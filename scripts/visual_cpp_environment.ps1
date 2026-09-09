function Test-VisualCppEnvironment {
    param(
        [AllowEmptyString()]
        [string]$IncludePath,

        [AllowEmptyString()]
        [string]$LibraryPath
    )

    $hasExceptionHeader = @($IncludePath -split ";" | Where-Object {
        $_ -and (Test-Path -LiteralPath (Join-Path $_ "excpt.h") -PathType Leaf)
    }).Count -gt 0
    $hasRuntimeLibrary = @($LibraryPath -split ";" | Where-Object {
        $_ -and (Test-Path -LiteralPath (Join-Path $_ "msvcrt.lib") -PathType Leaf)
    }).Count -gt 0
    return $hasExceptionHeader -and $hasRuntimeLibrary
}

function Initialize-VisualCppEnvironment {
    param(
        [string[]]$Candidates
    )

    if (Test-VisualCppEnvironment -IncludePath $env:INCLUDE -LibraryPath $env:LIB) {
        return "existing developer shell"
    }

    if (-not $PSBoundParameters.ContainsKey("Candidates")) {
        $foundCandidates = [System.Collections.Generic.List[string]]::new()
        if ($env:VSINSTALLDIR) {
            $candidate = Join-Path $env:VSINSTALLDIR "Common7\Tools\VsDevCmd.bat"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $foundCandidates.Add($candidate)
            }
        }
        $programRoots = @(
            [Environment]::GetFolderPath("ProgramFiles"),
            [Environment]::GetFolderPath("ProgramFilesX86")
        ) | Where-Object { $_ } | Select-Object -Unique
        foreach ($programRoot in $programRoots) {
            $pattern = Join-Path $programRoot "Microsoft Visual Studio\*\*\Common7\Tools\VsDevCmd.bat"
            foreach ($candidate in Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue) {
                $foundCandidates.Add($candidate.FullName)
            }
        }
        $Candidates = @($foundCandidates)
    }

    $orderedCandidates = @($Candidates | Where-Object {
        Test-Path -LiteralPath $_ -PathType Leaf
    } | Select-Object -Unique | Sort-Object {
        (Get-Item -LiteralPath $_).LastWriteTimeUtc
    } -Descending)
    foreach ($candidate in $orderedCandidates) {
        $lines = & cmd.exe /d /s /c "`"$candidate`" -arch=x64 -host_arch=x64 >nul && set"
        if ($LASTEXITCODE -ne 0) {
            continue
        }
        $candidateEnvironment = @{}
        foreach ($line in $lines) {
            $text = [string]$line
            if ($text.StartsWith("=")) {
                continue
            }
            $separator = $text.IndexOf("=")
            if ($separator -gt 0) {
                $candidateEnvironment[$text.Substring(0, $separator)] = $text.Substring($separator + 1)
            }
        }
        if (-not (Test-VisualCppEnvironment `
            -IncludePath ([string]$candidateEnvironment["INCLUDE"]) `
            -LibraryPath ([string]$candidateEnvironment["LIB"]))) {
            Write-Host "Skipping incomplete Visual C++ environment: $candidate" -ForegroundColor Yellow
            continue
        }
        foreach ($entry in $candidateEnvironment.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
        }
        return $candidate
    }

    $found = if ($orderedCandidates.Count) {
        "Found $($orderedCandidates.Count) Visual Studio developer environment(s), but none exposed both excpt.h and msvcrt.lib."
    }
    else {
        "No Visual Studio developer environment was found."
    }
    throw "$found Install or repair the Visual Studio Build Tools workload 'Desktop development with C++' and a Windows 10/11 SDK."
}
