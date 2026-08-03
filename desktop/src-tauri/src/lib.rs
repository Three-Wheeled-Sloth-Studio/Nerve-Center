use std::{
    env,
    process::{Child, Command, Stdio},
    sync::Mutex,
};

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, RunEvent, WindowEvent,
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

struct ApiProcess(Mutex<Option<Child>>);

pub fn run() {
    let app = tauri::Builder::default()
        .manage(ApiProcess(Mutex::new(None)))
        .setup(|app| {
            if let Some(child) = spawn_api() {
                *app.state::<ApiProcess>().0.lock().expect("API process lock") = Some(child);
            }

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

fn spawn_api() -> Option<Child> {
    if env::var("NERVE_CENTER_API_MANAGED").as_deref() == Ok("0") {
        return None;
    }
    let python = env::var("NERVE_CENTER_PYTHON").unwrap_or_else(|_| "python".to_string());
    let mut command = Command::new(python);
    command
        .args([
            "-c",
            "from nerve_center.api.app import run; run()",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    command.spawn().ok()
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn stop_api(app: &AppHandle) {
    if let Ok(mut process) = app.state::<ApiProcess>().0.lock() {
        if let Some(child) = process.as_mut() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *process = None;
    }
}
