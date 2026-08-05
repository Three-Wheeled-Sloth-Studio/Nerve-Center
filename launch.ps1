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
