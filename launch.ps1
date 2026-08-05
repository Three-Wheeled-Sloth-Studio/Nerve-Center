[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopRoot = Join-Path $repoRoot "desktop"
$venvRoot = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"

function Require-Command {
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [Parameter(Mandatory)]
        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required. $InstallHint"
    }
}

function Get-NerveCenterHealth {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 1
    }
    catch {
        return $null
    }
}

function Test-NerveCenterManager {
    try {
        $modules = @(Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/v1/modules" -TimeoutSec 2)
        return [bool]($modules | Where-Object {
            $_.manifest.module_id -eq "job_scout"
        } | Select-Object -First 1)
    }
    catch {
        return $false
    }
}

function Test-JobScoutWorkspace {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/v1/modules/job_scout/workspace" -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Stop-NerveCenterProcessTree {
    param(
        [Parameter(Mandatory)]
        [int]$ApiProcessId
    )

    $apiProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ApiProcessId" -ErrorAction SilentlyContinue
    if ($null -ne $apiProcess -and $apiProcess.ParentProcessId) {
        $parentProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($apiProcess.ParentProcessId)" -ErrorAction SilentlyContinue
        if ($null -ne $parentProcess -and [string]$parentProcess.Name -ieq "nerve-center-desktop.exe") {
            Stop-Process -Id $parentProcess.ProcessId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 200
        }
    }

    Stop-Process -Id $ApiProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-StaleNerveCenterApi {
    param(
        [Parameter(Mandatory)]
        [string]$ExpectedVersion
    )

    $health = Get-NerveCenterHealth
    if ($null -eq $health -or [string]$health.status -ne "ok") {
        return
    }
    if (-not (Test-NerveCenterManager)) {
        return
    }

    $runningVersion = [string]$health.version
    $workspaceAvailable = Test-JobScoutWorkspace
    if ($runningVersion -eq $ExpectedVersion -and $workspaceAvailable) {
        return
    }
    if ($env:NERVE_CENTER_API_MANAGED -eq "0") {
        throw "The externally managed Nerve Center API on port 8765 is stale. Restart that API before launching the desktop shell."
    }

    $reason = if ($runningVersion -ne $ExpectedVersion) {
        "version $runningVersion is running; this checkout requires $ExpectedVersion"
    }
    else {
        "the running API does not expose the current Job Scout workspace contract"
    }
    Write-Host "Stopping stale Nerve Center API: $reason." -ForegroundColor Yellow

    $listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $listener -or $null -eq $listener.OwningProcess) {
        throw "A stale Nerve Center API is responding on port 8765, but its process could not be identified. Quit Nerve Center from the system tray, then run launch.bat again."
    }

    Stop-NerveCenterProcessTree -ApiProcessId $listener.OwningProcess
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 100
        if ($null -eq (Get-NerveCenterHealth)) {
            return
        }
    }
    throw "The stale Nerve Center API did not release port 8765. Quit it from the system tray, then run launch.bat again."
}

Write-Host "Nerve Center source launcher" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot"

Require-Command -Name "node" -InstallHint "Install Node.js 22 or newer and add it to PATH."
Require-Command -Name "npm" -InstallHint "Install npm with Node.js and add it to PATH."
Require-Command -Name "cargo" -InstallHint "Install the stable Rust toolchain from https://rustup.rs/."

$nodeMajor = [int]((& node --version).TrimStart("v").Split(".")[0])
if ($nodeMajor -lt 22) {
    throw "Node.js 22 or newer is required; found $(& node --version)."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($SkipInstall) {
        throw "The repository virtual environment is missing. Run launch.bat without -SkipInstall once."
    }

    Require-Command -Name "python" -InstallHint "Install Python 3.12 or newer and add it to PATH."
    $systemPythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ([version]$systemPythonVersion -lt [version]"3.12") {
        throw "Python 3.12 or newer is required to create .venv; found $systemPythonVersion."
    }

    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    & python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Python virtual-environment creation failed."
    }
}

$venvPythonVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$venvPythonVersion -lt [version]"3.12") {
    throw "The repository .venv must use Python 3.12 or newer; found $venvPythonVersion. Remove .venv and recreate it with a newer Python installation."
}

& $venvPython -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    if ($SkipInstall) {
        throw "pip is missing from the repository .venv. Run launch.bat without -SkipInstall once."
    }

    Write-Host "Restoring pip in the Python virtual environment..." -ForegroundColor Yellow
    & $venvPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restore pip in the repository virtual environment."
    }
}

$checkoutVersion = Select-String -Path (Join-Path $repoRoot "pyproject.toml") -Pattern '^version\s*=\s*"([^"]+)"' |
    Select-Object -First 1 |
    ForEach-Object { $_.Matches[0].Groups[1].Value }
Stop-StaleNerveCenterApi -ExpectedVersion $checkoutVersion

$installedVersion = & $venvPython -c "import importlib.metadata; print(importlib.metadata.version('nerve-center'))" 2>$null
$packageNeedsInstall = $LASTEXITCODE -ne 0 -or $installedVersion -ne $checkoutVersion

if ($packageNeedsInstall) {
    if ($SkipInstall) {
        throw "The Nerve Center Python package in .venv is missing or stale (installed: $installedVersion; checkout: $checkoutVersion). Run launch.bat without -SkipInstall."
    }

    Write-Host "Installing Nerve Center $checkoutVersion and Python dependencies..." -ForegroundColor Yellow
    & $venvPython -m pip install -e $repoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependency installation failed."
    }
}

$nodeModules = Join-Path $desktopRoot "node_modules"
if (-not (Test-Path -LiteralPath $nodeModules)) {
    if ($SkipInstall) {
        throw "Desktop dependencies are missing. Run launch.bat without -SkipInstall once."
    }

    Write-Host "Installing desktop dependencies..." -ForegroundColor Yellow
    Push-Location $desktopRoot
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) {
            throw "Desktop dependency installation failed."
        }
    }
    finally {
        Pop-Location
    }
}

$ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Warning "Ollama is not installed or not on PATH. The app will launch, but live local-model work will be unavailable."
}
else {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
    }
    catch {
        Write-Warning "Ollama is installed but its local service is not responding. Start Ollama before testing model-backed work."
    }
}

$env:NERVE_CENTER_PYTHON = $venvPython
Write-Host "Starting Nerve Center..." -ForegroundColor Green
Write-Host "Managed API: http://127.0.0.1:8765"

Push-Location $desktopRoot
try {
    & npm run tauri dev
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri development launch failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
