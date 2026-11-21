#Requires -Version 5.1
param(
    [ValidateSet("RC1Archival", "RC2Release")]
    [string]$Mode = "RC1Archival",
    [switch]$DryRun,
    [string]$RepoPath = "C:\Projects\ERPWorktrees\ERP-RC1",
    [string]$Branch = "rc1/20261119",
    [string]$ExpectedHead = "939e91b915bcde6c0b96078d20377804849f57c8",
    [string]$BaseCommit = "f64ef969de9428445afbfb854fe5311cd47db1cf",
    [string]$RemoteUrl = "https://github.com/Eli-Mira/erp-medical-dms.git",
    [string]$ExpectedProtectedPatchSha256 = "e28fbbbf420d3f1f2b55491b272a4028cb0c8d99c995874710b3a209a19180c2"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [string]$Exe,
        [string[]]$CmdArgs
    )
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $Exe @CmdArgs 2>&1
        $rc = $LASTEXITCODE
        [pscustomobject]@{
            ExitCode = $rc
            Output   = ($raw | Out-String).Trim()
        }
    } finally {
        $ErrorActionPreference = $old
    }
}

function Get-ProcessStdoutSha256 {
    param(
        [string]$Exe,
        [string[]]$CmdArgs
    )
    $p = $null
    $ms = $null
    $hasher = $null
    try {
        $p = New-Object System.Diagnostics.Process
        $p.StartInfo.FileName = $Exe
        $p.StartInfo.UseShellExecute = $false
        $p.StartInfo.RedirectStandardOutput = $true
        $p.StartInfo.RedirectStandardError = $true
        $p.StartInfo.CreateNoWindow = $true
        $argList = @()
        foreach ($arg in $CmdArgs) {
            if ($arg -match '\s') {
                $argList += "`"$arg`""
            } else {
                $argList += $arg
            }
        }
        $p.StartInfo.Arguments = $argList -join ' '
        $ms = New-Object System.IO.MemoryStream
        [void]$p.Start()
        $stderrTask = $p.StandardError.ReadToEndAsync()
        [void]$p.StandardOutput.BaseStream.CopyTo($ms)
        [void]$stderrTask.Wait()
        [void]$p.WaitForExit()
        if ($p.ExitCode -ne 0) {
            throw "Process '$Exe' exited with code $($p.ExitCode)"
        }
        $hasher = [System.Security.Cryptography.SHA256]::Create()
        $hashBytes = $hasher.ComputeHash($ms.ToArray())
        [System.BitConverter]::ToString($hashBytes).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($hasher) { $hasher.Dispose() }
        if ($ms) { $ms.Dispose() }
        if ($p) { $p.Dispose() }
    }
}

function Get-FileSha256Lower {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$SwarmRoot = Split-Path -Parent $PSScriptRoot
$ReviewsDir = Join-Path $SwarmRoot "shared\reviews"
$LogDir = Join-Path $ReviewsDir "CLAUDE_EVIDENCE_20261121"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $LogDir "push_if_signed_${timestamp}_${Mode}.log"
$logShaFile = "${logFile}.sha256"

try {
    $logContent = @()
    $logContent += "Mode: $Mode"
    $logContent += "DryRun: $DryRun"
    $logContent += "RepoPath: $RepoPath"
    $logContent += "Branch: $Branch"
    $logContent += "ExpectedHead: $ExpectedHead"
    $logContent += "BaseCommit: $BaseCommit"
    $logContent += "RemoteUrl: $RemoteUrl"
    $logContent += "ExpectedProtectedPatchSha256: $ExpectedProtectedPatchSha256"
    $logContent += "---"

    if ($Branch -match '^(master|main|prod/)') {
        throw "Branch '$Branch' matches forbidden pattern"
    }

    if (-not (Test-Path -LiteralPath $RepoPath -PathType Container)) {
        throw "RepoPath '$RepoPath' does not exist or is not a directory"
    }

    $gitStatus = Invoke-Native "git" @("-C", $RepoPath, "status", "--porcelain")
    if ($gitStatus.ExitCode -ne 0) {
        throw "git status failed with exit code $($gitStatus.ExitCode): $($gitStatus.Output)"
    }
    if ($gitStatus.Output -ne "") {
        throw "Working directory is not clean: $($gitStatus.Output)"
    }

    $gitBranch = Invoke-Native "git" @("-C", $RepoPath, "branch", "--show-current")
    if ($gitBranch.ExitCode -ne 0) {
        throw "git branch failed with exit code $($gitBranch.ExitCode): $($gitBranch.Output)"
    }
    if ($gitBranch.Output -ne $Branch) {
        throw "Current branch '$($gitBranch.Output)' does not match expected '$Branch'"
    }

    $gitRevParse = Invoke-Native "git" @("-C", $RepoPath, "rev-parse", "HEAD")
    if ($gitRevParse.ExitCode -ne 0) {
        throw "git rev-parse HEAD failed with exit code $($gitRevParse.ExitCode): $($gitRevParse.Output)"
    }
    if ($gitRevParse.Output -ne $ExpectedHead) {
        throw "HEAD '$($gitRevParse.Output)' does not match expected '$ExpectedHead'"
    }

    $gitMergeBase = Invoke-Native "git" @("-C", $RepoPath, "merge-base", "--is-ancestor", $BaseCommit, "HEAD")
    if ($gitMergeBase.ExitCode -ne 0) {
        throw "BaseCommit '$BaseCommit' is not ancestor of HEAD"
    }

    $gitRemoteUrl = Invoke-Native "git" @("-C", $RepoPath, "remote", "get-url", "origin")
    if ($gitRemoteUrl.ExitCode -ne 0) {
        throw "git remote get-url origin failed with exit code $($gitRemoteUrl.ExitCode): $($gitRemoteUrl.Output)"
    }
    if ($gitRemoteUrl.Output -ne $RemoteUrl) {
        throw "Remote URL '$($gitRemoteUrl.Output)' does not match expected '$RemoteUrl'"
    }
    if ($gitRemoteUrl.Output -match '(?i)(token|ghp_|github_pat_|x-access-token|@)') {
        throw "Remote URL contains authentication token pattern"
    }

    try {
        $webResult = Invoke-WebRequest -Uri "https://api.github.com/repos/Eli-Mira/erp-medical-dms" -Method Get -UseBasicParsing -ErrorAction Stop
        $logContent += "GitHub API status: $($webResult.StatusCode) $($webResult.StatusDescription) (INFO ONLY)"
    } catch {
        $logContent += "GitHub API request failed: $($_.Exception.Message)"
    }

    if ($Mode -eq "RC1Archival") {
        if ($Branch -ne "rc1/20261119") {
            throw "RC1Archival requires branch 'rc1/20261119', got '$Branch'"
        }
        if ($ExpectedHead -ne "939e91b915bcde6c0b96078d20377804849f57c8") {
            throw "RC1Archival requires ExpectedHead '939e91b915bcde6c0b96078d20377804849f57c8', got '$ExpectedHead'"
        }

        $r4File = Join-Path $ReviewsDir "CLAUDE__R4.md"
        $r4ShaFile = "${r4File}.sha256"
        if (-not (Test-Path -LiteralPath $r4File -PathType Leaf)) {
            throw "CLAUDE__R4.md not found in $ReviewsDir"
        }
        if (-not (Test-Path -LiteralPath $r4ShaFile -PathType Leaf)) {
            throw "CLAUDE__R4.md.sha256 not found in $ReviewsDir"
        }

        $sidecarContent = Get-Content -LiteralPath $r4ShaFile -Raw
        $sidecarHash = ($sidecarContent -split '\s')[0].Trim()
        $computedHash = Get-FileSha256Lower $r4File
        if ($computedHash -ne $sidecarHash.ToLowerInvariant()) {
            throw "SHA256 mismatch for CLAUDE__R4.md: computed '$computedHash', sidecar '$sidecarHash'"
        }

        $r4Content = Get-Content -LiteralPath $r4File -Raw
        if ($r4Content -notmatch 'ALL PASS') {
            throw "CLAUDE__R4.md does not contain 'ALL PASS'"
        }
        if ($r4Content -notmatch '0 TRUE SECRETS') {
            throw "CLAUDE__R4.md does not contain '0 TRUE SECRETS'"
        }
        if ($r4Content -notmatch $ExpectedHead) {
            throw "CLAUDE__R4.md does not contain ExpectedHead '$ExpectedHead'"
        }
    } elseif ($Mode -eq "RC2Release") {
        $requiredFiles = @(
            "CLAUDE__R1.md",
            "CLAUDE__R2.md",
            "CLAUDE__R4.md",
            "CLAUDE__R5.md",
            "CLAUDE__R6.md",
            "CLAUDE__R7_V2_LEDGER_VERIFIED.md",
            "CLAUDE__R8.md",
            "CLAUDE__R9.md"
        )
        foreach ($file in $requiredFiles) {
            $fullPath = Join-Path $ReviewsDir $file
            $shaPath = "${fullPath}.sha256"
            if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
                throw "$file not found in $ReviewsDir"
            }
            if (-not (Test-Path -LiteralPath $shaPath -PathType Leaf)) {
                throw "$file.sha256 not found in $ReviewsDir"
            }
            $sidecarContent = Get-Content -LiteralPath $shaPath -Raw
            $sidecarHash = ($sidecarContent -split '\s')[0].Trim()
            $computedHash = Get-FileSha256Lower $fullPath
            if ($computedHash -ne $sidecarHash.ToLowerInvariant()) {
                throw "SHA256 mismatch for ${file}: computed '$computedHash', sidecar '$sidecarHash'"
            }
            $fileContent = Get-Content -LiteralPath $fullPath -Raw
            if ($fileContent -notmatch 'SIGN') {
                throw "$file does not contain 'SIGN'"
            }
            if ($fileContent -match 'NEEDS-CLAUDE-MODEL-COUNTERSIGN') {
                throw "$file contains 'NEEDS-CLAUDE-MODEL-COUNTERSIGN'"
            }
            if ($fileContent -match 'NO-SIGN') {
                throw "$file contains 'NO-SIGN'"
            }
            if ($fileContent -notmatch $ExpectedHead) {
                throw "$file does not contain ExpectedHead '$ExpectedHead'"
            }
        }
    }

    $gitleaks = Join-Path $SwarmRoot "S3\gitleaks.exe"
    if (-not (Test-Path -LiteralPath $gitleaks -PathType Leaf)) {
        throw "gitleaks.exe not found at $gitleaks"
    }
    $gitleaksHash = Get-FileSha256Lower $gitleaks
    if ($gitleaksHash -ne "8f397272f513c00b573f50380c4724e4b3ac759be1de313d907bb968c5d14c09") {
        throw "gitleaks.exe SHA256 mismatch: expected 8f397272f513c00b573f50380c4724e4b3ac759be1de313d907bb968c5d14c09, got $gitleaksHash"
    }

    $gitleaksVersion = Invoke-Native $gitleaks @("version")
    $logContent += "gitleaks version: $($gitleaksVersion.Output)"
    $logContent += "gitleaks config: default built-in; no .gitleaks.toml"

    $tempJson = Join-Path $env:TEMP "gitleaks_$([Guid]::NewGuid().ToString()).json"
    try {
        $gitleaksCmd = @(
            "git",
            "--log-opts", "$BaseCommit..$ExpectedHead",
            "--redact",
            "--no-banner",
            "--report-format", "json",
            "--report-path", $tempJson,
            "--exit-code", "2",
            $RepoPath
        )
        $logContent += "gitleaks command: $gitleaks $($gitleaksCmd -join ' ')"
        $gitleaksRun = Invoke-Native $gitleaks $gitleaksCmd
        if ($gitleaksRun.ExitCode -ne 0) {
            throw "gitleaks scan failed with exit code $($gitleaksRun.ExitCode): $($gitleaksRun.Output)"
        }
        if (Test-Path -LiteralPath $tempJson -PathType Leaf) {
            $jsonContent = Get-Content -LiteralPath $tempJson -Raw
            $trimmed = $jsonContent.Trim()
            if ($trimmed -ne "" -and $trimmed -ne "[]" -and $trimmed -ne "null") {
                $parsed = @($trimmed | ConvertFrom-Json)
                if ($parsed.Count -gt 0) {
                    throw "gitleaks found $($parsed.Count) secrets"
                }
            }
        }
    } finally {
        Remove-Item -LiteralPath $tempJson -ErrorAction SilentlyContinue
    }

    $gitLog = Invoke-Native "git" @("-C", $RepoPath, "log", "--format=%H|%an|%ae|%cn|%ce", "$BaseCommit..$ExpectedHead")
    if ($gitLog.ExitCode -ne 0) {
        throw "git log failed with exit code $($gitLog.ExitCode): $($gitLog.Output)"
    }
    $lines = @($gitLog.Output -split '\r?\n' | Where-Object { $_ -ne "" })
    if ($lines.Count -lt 1) {
        throw "No commits in range $BaseCommit..$ExpectedHead"
    }
    foreach ($line in $lines) {
        $parts = @($line -split '\|')
        if ($parts.Count -ne 5) {
            throw "Invalid log line format: $line"
        }
        if ($parts[1] -ne "Eli-Mira") {
            throw "Author name mismatch in commit $($parts[0]): expected 'Eli-Mira', got '$($parts[1])'"
        }
        if ($parts[2] -ne "242167870+Eli-Mira@users.noreply.github.com") {
            throw "Author email mismatch in commit $($parts[0]): expected '242167870+Eli-Mira@users.noreply.github.com', got '$($parts[2])'"
        }
        if ($parts[3] -ne "Eli-Mira") {
            throw "Committer name mismatch in commit $($parts[0]): expected 'Eli-Mira', got '$($parts[3])'"
        }
        if ($parts[4] -ne "242167870+Eli-Mira@users.noreply.github.com") {
            throw "Committer email mismatch in commit $($parts[0]): expected '242167870+Eli-Mira@users.noreply.github.com', got '$($parts[4])'"
        }
    }

    $protectedFiles = @("Dockerfile", "docker-compose.yml", "requirements.txt", "app/config.py", "app/db.py", "alembic/env.py")
    $diffArgs = @("-C", $RepoPath, "diff", "$BaseCommit..$ExpectedHead", "--") + $protectedFiles
    $patchSha = Get-ProcessStdoutSha256 "git" $diffArgs
    $logContent += "Protected files raw LF diff SHA256: $patchSha"
    if ($Mode -eq "RC1Archival" -and $patchSha -ne $ExpectedProtectedPatchSha256) {
        throw "Protected files patch SHA256 mismatch: expected '$ExpectedProtectedPatchSha256', got '$patchSha'"
    }

    if ($Mode -eq "RC1Archival") {
        $appDiff = Invoke-Native "git" @("-C", $RepoPath, "diff", "--name-only", "$BaseCommit..$ExpectedHead", "--", "app", "tests", "alembic", "scripts", "web")
        if ($appDiff.ExitCode -ne 0) {
            throw "git diff --name-only failed with exit code $($appDiff.ExitCode): $($appDiff.Output)"
        }
        if ($appDiff.Output -ne "") {
            throw "Found changes in app/tests/alembic/scripts/web: $($appDiff.Output)"
        }
    }

    $allChanged = Invoke-Native "git" @("-C", $RepoPath, "diff", "--name-only", "$BaseCommit..$ExpectedHead")
    if ($allChanged.ExitCode -ne 0) {
        throw "git diff --name-only failed with exit code $($allChanged.ExitCode): $($allChanged.Output)"
    }
    $forbiddenPattern = '(?i)(\.env($|\.)|\.xlsx$|\.xls$|\.dump$|\.bak$|\.csv$)'
    foreach ($changedFile in ($allChanged.Output -split '\r?\n' | Where-Object { $_ -ne "" })) {
        if ($changedFile -match $forbiddenPattern -and $changedFile -ne 'docs/unreviewed/SQL_RUNBOOK_V2_UNREVIEWED.sql') {
            throw "Changed file '$changedFile' matches forbidden pattern"
        }
    }

    if ($DryRun) {
        $logContent += "DRY_RUN_PASS: all checks passed; no push executed."
        $logContent | Out-File -LiteralPath $logFile -Encoding UTF8
        $logHash = Get-FileSha256Lower $logFile
        Set-Content -LiteralPath $logShaFile -Encoding UTF8 -Value "$logHash  $(Split-Path -Leaf $logFile)"
        return
    }

    try {
        $env:ELI_PUSH_OK = "1"
        $gitPush = Invoke-Native "git" @("-C", $RepoPath, "push", $RemoteUrl, "${Branch}:refs/heads/${Branch}")
        if ($gitPush.ExitCode -ne 0) {
            throw "git push failed with exit code $($gitPush.ExitCode): $($gitPush.Output)"
        }
        $lsRemote = Invoke-Native "git" @("-C", $RepoPath, "ls-remote", "--heads", $RemoteUrl, "refs/heads/${Branch}")
        if ($lsRemote.ExitCode -ne 0) {
            throw "git ls-remote failed with exit code $($lsRemote.ExitCode): $($lsRemote.Output)"
        }
        $remoteSha = ($lsRemote.Output -split '\s+')[0]
        if ($remoteSha -ne $ExpectedHead) {
            throw "Remote SHA '$remoteSha' does not match expected '$ExpectedHead'"
        }
        $logContent += "PUSH_VERIFIED_OK"
    } finally {
        Remove-Item Env:ELI_PUSH_OK -ErrorAction SilentlyContinue
    }
} catch {
    $logContent += "ERROR: $($_.Exception.Message)"
    throw
} finally {
    $logContent | Out-File -LiteralPath $logFile -Encoding UTF8
    $logHash = Get-FileSha256Lower $logFile
    Set-Content -LiteralPath $logShaFile -Encoding UTF8 -Value "$logHash  $(Split-Path -Leaf $logFile)"
}
