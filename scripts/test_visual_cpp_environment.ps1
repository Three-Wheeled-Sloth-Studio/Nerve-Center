$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "visual_cpp_environment.ps1")

$fixtureRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("nerve-center-msvc-" + [guid]::NewGuid())
$incompleteRoot = Join-Path $fixtureRoot "incomplete"
$completeRoot = Join-Path $fixtureRoot "complete"
$savedInclude = $env:INCLUDE
$savedLib = $env:LIB
try {
    New-Item -ItemType Directory -Path (Join-Path $incompleteRoot "include"), (Join-Path $incompleteRoot "lib"), (Join-Path $completeRoot "include"), (Join-Path $completeRoot "lib") -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $completeRoot "include\excpt.h"), (Join-Path $completeRoot "lib\msvcrt.lib") -Force | Out-Null
    $incomplete = Join-Path $incompleteRoot "VsDevCmd.bat"
    $complete = Join-Path $completeRoot "VsDevCmd.bat"
    Set-Content -LiteralPath $incomplete -Value "@set INCLUDE=$incompleteRoot\include`r`n@set LIB=$incompleteRoot\lib"
    Set-Content -LiteralPath $complete -Value "@set INCLUDE=$completeRoot\include`r`n@set LIB=$completeRoot\lib"

    $env:INCLUDE = ""
    $env:LIB = ""
    $selected = Initialize-VisualCppEnvironment -Candidates @($incomplete, $complete)
    if ($selected -ne $complete) {
        throw "Expected complete fixture toolchain; selected $selected"
    }
    if (-not (Test-VisualCppEnvironment -IncludePath $env:INCLUDE -LibraryPath $env:LIB)) {
        throw "Selected fixture did not initialize a usable Visual C++ environment."
    }
    if ((Initialize-VisualCppEnvironment -Candidates @($incomplete)) -ne "existing developer shell") {
        throw "An existing complete developer environment should be preserved."
    }

    $env:INCLUDE = ""
    $env:LIB = ""
    try {
        Initialize-VisualCppEnvironment -Candidates @($incomplete) | Out-Null
        throw "An incomplete-only candidate set should fail."
    }
    catch {
        if ($_.Exception.Message -notlike "*none exposed both excpt.h and msvcrt.lib*") {
            throw
        }
    }
    Write-Host "Visual C++ environment selection checks passed."
}
finally {
    $env:INCLUDE = $savedInclude
    $env:LIB = $savedLib
    Remove-Item -LiteralPath $fixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
