use std::{
    env,
    fs::{self, OpenOptions},
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicU64, Ordering},
        Mutex,
    },
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use serde::Serialize;
use tauri::{
    menu::{Menu, MenuItem},
    path::BaseDirectory,
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, RunEvent, State, WindowEvent,
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const API_ADDRESS: &str = "127.0.0.1:8765";
const API_HEALTH_REQUEST: &[u8] =
    b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
const STARTUP_ATTEMPTS: usize = 160;
const STARTUP_POLL_INTERVAL: Duration = Duration::from_millis(250);
const MONITOR_INTERVAL: Duration = Duration::from_secs(2);

#[cfg(windows)]
const BUNDLED_BACKEND: &str = "nerve-center-api.exe";
#[cfg(not(windows))]
const BUNDLED_BACKEND: &str = "nerve-center-api";

struct ApiRuntime {
    process: Mutex<Option<Child>>,
    status: Mutex<StartupStatus>,
    generation: AtomicU64,
}

impl ApiRuntime {
    fn new() -> Self {
        Self {
            process: Mutex::new(None),
            status: Mutex::new(StartupStatus::new(
                "starting",
                "Preparing the local service.",
            )),
            generation: AtomicU64::new(0),
        }
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct StartupStatus {
    phase: String,
    message: String,
    detail: Option<String>,
    backend_source: Option<String>,
    log_path: Option<String>,
    pid: Option<u32>,
    updated_at_ms: u64,
}

impl StartupStatus {
    fn new(phase: &str, message: &str) -> Self {
        Self {
            phase: phase.to_string(),
            message: message.to_string(),
            detail: None,
            backend_source: None,
            log_path: None,
            pid: None,
            updated_at_ms: now_ms(),
        }
    }

    fn detail(mut self, detail: impl Into<String>) -> Self {
        self.detail = Some(detail.into());
        self
    }

    fn source(mut self, source: impl Into<String>) -> Self {
        self.backend_source = Some(source.into());
        self
    }

    fn log_path(mut self, path: Option<&PathBuf>) -> Self {
        self.log_path = path.map(|item| item.to_string_lossy().into_owned());
        self
    }

    fn pid(mut self, pid: Option<u32>) -> Self {
        self.pid = pid;
        self
    }
}

struct SpawnedBackend {
    child: Child,
    source: String,
    log_path: PathBuf,
}

#[derive(Debug, PartialEq, Eq)]
enum HealthProbe {
    Healthy,
    Unreachable,
    Occupied(String),
}

#[tauri::command]
fn startup_status(runtime: State<'_, ApiRuntime>) -> StartupStatus {
    runtime
        .status
        .lock()
        .expect("startup status lock")
        .clone()
}

#[tauri::command]
fn restart_api(app: AppHandle) -> Result<(), String> {
    stop_api(&app);
    start_api(app);
    Ok(())
}

#[tauri::command]
fn diagnostic_log_path(runtime: State<'_, ApiRuntime>) -> Option<String> {
    runtime
        .status
        .lock()
        .expect("startup status lock")
        .log_path
        .clone()
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(ApiRuntime::new())
        .invoke_handler(tauri::generate_handler![
            startup_status,
            restart_api,
            diagnostic_log_path
        ])
        .setup(|app| {
            let show_item =
                MenuItem::with_id(app, "show", "Show Nerve Center", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;
            let mut tray = TrayIconBuilder::new()
                .menu(&menu)
                .show_menu_on_left_click(false)
                .tooltip("Nerve Center")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => show_main_window(app),
                    "quit" => {
                        stop_api(app);
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_main_window(tray.app_handle());
                    }
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;

            start_api(app.handle().clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build Nerve Center desktop shell");

    app.run(|app_handle, event| {
        if let RunEvent::ExitRequested { .. } = event {
            stop_api(app_handle);
        }
    });
}

fn start_api(app: AppHandle) {
    let runtime = app.state::<ApiRuntime>();
    let generation = runtime.generation.fetch_add(1, Ordering::SeqCst) + 1;
    set_status(
        &app,
        generation,
        StartupStatus::new("starting", "Preparing the local service."),
    );

    thread::spawn(move || supervise_api(app, generation));
}

fn supervise_api(app: AppHandle, generation: u64) {
    let managed = env::var("NERVE_CENTER_API_MANAGED").as_deref() != Ok("0");

    match probe_health() {
        HealthProbe::Healthy => {
            set_status(
                &app,
                generation,
                StartupStatus::new("ready", "Connected to the local service.")
                    .source("existing service"),
            );
            monitor_api(&app, generation, false);
            return;
        }
        HealthProbe::Occupied(detail) => {
            set_status(
                &app,
                generation,
                StartupStatus::new("failed", "Port 8765 is already in use.")
                    .detail(detail)
                    .source("port conflict"),
            );
            return;
        }
        HealthProbe::Unreachable => {}
    }

    if !managed {
        set_status(
            &app,
            generation,
            StartupStatus::new(
                "waitingForHealth",
                "Waiting for the externally managed local service.",
            )
            .source("external service"),
        );
        wait_for_health(&app, generation, false, None);
        return;
    }

    let spawned = match spawn_backend(&app) {
        Ok(spawned) => spawned,
        Err(error) => {
            set_status(
                &app,
                generation,
                StartupStatus::new("failed", "The local service could not be started.")
                    .detail(error),
            );
            return;
        }
    };

    let pid = spawned.child.id();
    let source = spawned.source.clone();
    let log_path = spawned.log_path.clone();
    {
        let runtime = app.state::<ApiRuntime>();
        if runtime.generation.load(Ordering::SeqCst) != generation {
            let mut child = spawned.child;
            let _ = child.kill();
            let _ = child.wait();
            return;
        }
        *runtime.process.lock().expect("API process lock") = Some(spawned.child);
    }

    set_status(
        &app,
        generation,
        StartupStatus::new(
            "waitingForHealth",
            "Initializing local storage and the task scheduler.",
        )
        .source(source)
        .log_path(Some(&log_path))
        .pid(Some(pid)),
    );
    wait_for_health(&app, generation, true, Some(log_path));
}

fn wait_for_health(
    app: &AppHandle,
    generation: u64,
    owns_process: bool,
    log_path: Option<PathBuf>,
) {
    for _ in 0..STARTUP_ATTEMPTS {
        if !is_current_generation(app, generation) {
            return;
        }

        if owns_process {
            match managed_process_exit(app) {
                Ok(Some(code)) => {
                    set_status(
                        app,
                        generation,
                        StartupStatus::new(
                            "failed",
                            "The local service exited before it became ready.",
                        )
                        .detail(format!("Process exit code: {code}"))
                        .log_path(log_path.as_ref()),
                    );
                    return;
                }
                Err(error) => {
                    set_status(
                        app,
                        generation,
                        StartupStatus::new(
                            "failed",
                            "The local service process could not be inspected.",
                        )
                        .detail(error)
                        .log_path(log_path.as_ref()),
                    );
                    return;
                }
                Ok(None) => {}
            }
        }

        match probe_health() {
            HealthProbe::Healthy => {
                let current = app.state::<ApiRuntime>();
                let prior = current
                    .status
                    .lock()
                    .expect("startup status lock")
                    .clone();
                let pid = prior.pid;
                let source = prior
                    .backend_source
                    .unwrap_or_else(|| "local service".to_string());
                set_status(
                    app,
                    generation,
                    StartupStatus::new("ready", "Nerve Center is ready.")
                        .source(source)
                        .log_path(log_path.as_ref())
                        .pid(pid),
                );
                monitor_api(app, generation, owns_process);
                return;
            }
            HealthProbe::Occupied(detail) => {
                if owns_process {
                    terminate_managed_process(app);
                }
                set_status(
                    app,
                    generation,
                    StartupStatus::new(
                        "failed",
                        "Port 8765 responded, but not as Nerve Center.",
                    )
                    .detail(detail)
                    .log_path(log_path.as_ref()),
                );
                return;
            }
            HealthProbe::Unreachable => thread::sleep(STARTUP_POLL_INTERVAL),
        }
    }

    if owns_process {
        terminate_managed_process(app);
    }
    set_status(
        app,
        generation,
        StartupStatus::new("failed", "The local service did not become ready in time.")
            .detail("Health check timed out after 40 seconds.")
            .log_path(log_path.as_ref()),
    );
}

fn monitor_api(app: &AppHandle, generation: u64, owns_process: bool) {
    let mut failed_probes = 0;
    loop {
        if !is_current_generation(app, generation) {
            return;
        }
        thread::sleep(MONITOR_INTERVAL);

        if owns_process {
            match managed_process_exit(app) {
                Ok(Some(code)) => {
                    let current = app.state::<ApiRuntime>();
                    let prior = current
                        .status
                        .lock()
                        .expect("startup status lock")
                        .clone();
                    let source = prior
                        .backend_source
                        .unwrap_or_else(|| "managed service".to_string());
                    let log_path = prior.log_path.map(PathBuf::from);
                    set_status(
                        app,
                        generation,
                        StartupStatus::new("failed", "The local service stopped unexpectedly.")
                            .detail(format!("Process exit code: {code}"))
                            .source(source)
                            .log_path(log_path.as_ref()),
                    );
                    return;
                }
                Err(error) => {
                    set_status(
                        app,
                        generation,
                        StartupStatus::new("failed", "The service process became unavailable.")
                            .detail(error),
                    );
                    return;
                }
                Ok(None) => {}
            }
        }

        match probe_health() {
            HealthProbe::Healthy => failed_probes = 0,
            HealthProbe::Unreachable | HealthProbe::Occupied(_) => {
                failed_probes += 1;
                if failed_probes >= 3 {
                    if owns_process {
                        terminate_managed_process(app);
                    }
                    let current = app.state::<ApiRuntime>();
                    let prior = current
                        .status
                        .lock()
                        .expect("startup status lock")
                        .clone();
                    let source = prior
                        .backend_source
                        .unwrap_or_else(|| "local service".to_string());
                    let log_path = prior.log_path.map(PathBuf::from);
                    set_status(
                        app,
                        generation,
                        StartupStatus::new("failed", "The local service is no longer healthy.")
                            .detail("Three consecutive health checks failed.")
                            .source(source)
                            .log_path(log_path.as_ref()),
                    );
                    return;
                }
            }
        }
    }
}

fn spawn_backend(app: &AppHandle) -> Result<SpawnedBackend, String> {
    let log_path = backend_log_path(app)?;
    let log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|error| format!("Could not open backend log: {error}"))?;
    let stdout = log
        .try_clone()
        .map_err(|error| format!("Could not clone backend log handle: {error}"))?;

    let (mut command, source) = backend_command(app)?;
    command
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(log));
    #[cfg(windows)]
    command.creation_flags(0x08000000);

    let child = command
        .spawn()
        .map_err(|error| format!("Could not launch {source}: {error}"))?;
    Ok(SpawnedBackend {
        child,
        source,
        log_path,
    })
}

fn backend_command(app: &AppHandle) -> Result<(Command, String), String> {
    if let Ok(path) = env::var("NERVE_CENTER_API_EXECUTABLE") {
        let executable = PathBuf::from(&path);
        if !executable.is_file() {
            return Err(format!(
                "NERVE_CENTER_API_EXECUTABLE does not point to a file: {path}"
            ));
        }
        return Ok((Command::new(executable), "configured executable".to_string()));
    }

    if let Ok(executable) = app.path().resolve(BUNDLED_BACKEND, BaseDirectory::Resource) {
        if executable.is_file() {
            return Ok((Command::new(executable), "packaged backend".to_string()));
        }
    }

    let python = env::var("NERVE_CENTER_PYTHON").unwrap_or_else(|_| "python".to_string());
    let mut command = Command::new(&python);
    command.args(["-c", "from nerve_center.api.app import run; run()"]);
    Ok((command, format!("Python development fallback ({python})")))
}

fn backend_log_path(app: &AppHandle) -> Result<PathBuf, String> {
    let directory = app
        .path()
        .app_log_dir()
        .unwrap_or_else(|_| env::temp_dir().join("Nerve Center").join("logs"));
    fs::create_dir_all(&directory)
        .map_err(|error| format!("Could not create the local log directory: {error}"))?;
    Ok(directory.join("backend.log"))
}

fn managed_process_exit(app: &AppHandle) -> Result<Option<String>, String> {
    let runtime = app.state::<ApiRuntime>();
    let mut process = runtime.process.lock().expect("API process lock");
    let Some(child) = process.as_mut() else {
        return Ok(Some("process handle missing".to_string()));
    };
    match child.try_wait() {
        Ok(Some(status)) => {
            *process = None;
            Ok(Some(
                status
                    .code()
                    .map(|code| code.to_string())
                    .unwrap_or_else(|| "terminated by signal".to_string()),
            ))
        }
        Ok(None) => Ok(None),
        Err(error) => Err(error.to_string()),
    }
}

fn terminate_managed_process(app: &AppHandle) {
    let runtime = app.state::<ApiRuntime>();
    let mut process = runtime.process.lock().expect("API process lock");
    if let Some(child) = process.as_mut() {
        let _ = child.kill();
        let _ = child.wait();
    }
    *process = None;
}

fn stop_api(app: &AppHandle) {
    let runtime = app.state::<ApiRuntime>();
    runtime.generation.fetch_add(1, Ordering::SeqCst);
    terminate_managed_process(app);
    *runtime.status.lock().expect("startup status lock") =
        StartupStatus::new("stopped", "The local service is stopped.");
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn probe_health() -> HealthProbe {
    let address: SocketAddr = API_ADDRESS.parse().expect("valid local API address");
    let mut stream = match TcpStream::connect_timeout(&address, Duration::from_millis(350)) {
        Ok(stream) => stream,
        Err(_) => return HealthProbe::Unreachable,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
    if stream.write_all(API_HEALTH_REQUEST).is_err() {
        return HealthProbe::Occupied(
            "The port accepted a connection but rejected the health request.".to_string(),
        );
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return HealthProbe::Occupied(
            "The port accepted a connection but did not return a readable health response."
                .to_string(),
        );
    }
    classify_health_response(&response)
}

fn classify_health_response(response: &str) -> HealthProbe {
    let is_ok = response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200");
    let is_nerve_center =
        response.contains("\"status\":\"ok\"") || response.contains("\"status\": \"ok\"");
    if is_ok && is_nerve_center {
        return HealthProbe::Healthy;
    }

    let first_line = response
        .lines()
        .next()
        .filter(|line| !line.is_empty())
        .unwrap_or("No HTTP status line was returned.");
    HealthProbe::Occupied(format!("Unexpected response: {first_line}"))
}

fn set_status(app: &AppHandle, generation: u64, status: StartupStatus) {
    let runtime = app.state::<ApiRuntime>();
    if runtime.generation.load(Ordering::SeqCst) == generation {
        *runtime.status.lock().expect("startup status lock") = status;
    }
}

fn is_current_generation(app: &AppHandle, generation: u64) -> bool {
    app.state::<ApiRuntime>()
        .generation
        .load(Ordering::SeqCst)
        == generation
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}

#[cfg(test)]
mod tests {
    use super::{classify_health_response, HealthProbe};

    #[test]
    fn recognizes_healthy_nerve_center_response() {
        let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"ok\",\"version\":\"0.6.0\"}";
        assert_eq!(classify_health_response(response), HealthProbe::Healthy);
    }

    #[test]
    fn rejects_non_nerve_center_service() {
        let response = "HTTP/1.1 200 OK\r\n\r\nhello";
        assert!(matches!(
            classify_health_response(response),
            HealthProbe::Occupied(_)
        ));
    }
}
