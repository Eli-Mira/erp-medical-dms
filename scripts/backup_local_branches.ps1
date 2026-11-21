<#
.SYNOPSIS
  Non-destructive 2-hour git bundle --all backup of all local branches (keep last 3 + sha256 sidecars).
  Never deletes or prunes any worktree or branch.
#>
param(
    [string]$RepoPath = "C:\Projects\ERPWorktrees\ERP-RC1",
    [string]$OutDir = "C:\Projects\ERP-Orchestration\local-branch-backups",
    [int]$KeepLast = 3
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bundle = Join-Path $OutDir "erp_all_refs_$ts.bundle"
$sidecar = "$bundle.sha256"

git -C $RepoPath bundle create $bundle --all
if ($LASTEXITCODE -ne 0) { throw "git bundle create failed (exit $LASTEXITCODE)" }

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$verifyOut = & git -C $RepoPath bundle verify $bundle 2>&1 | Out-String
$verifyRc = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($verifyRc -ne 0) { throw "git bundle verify failed (exit $verifyRc): $verifyOut" }

$hash = (Get-FileHash -Algorithm SHA256 $bundle).Hash.ToLower()
"$hash  $(Split-Path -Leaf $bundle)" | Set-Content -Encoding UTF8 -NoNewline -Path $sidecar
"`n" | Add-Content -Encoding UTF8 -NoNewline -Path $sidecar

# Keep only the last $KeepLast bundles (plus their sidecars)
$old = Get-ChildItem -Path $OutDir -Filter "erp_all_refs_*.bundle" | Sort-Object LastWriteTime -Descending | Select-Object -Skip $KeepLast
foreach ($f in $old) {
    Remove-Item -Force -Path $f.FullName
    $sc = "$($f.FullName).sha256"
    if (Test-Path $sc) { Remove-Item -Force -Path $sc }
}

$sz = (Get-Item $bundle).Length
$count = (Get-ChildItem -Path $OutDir -Filter "erp_all_refs_*.bundle").Count
Write-Output "BUNDLE_OK | path=$bundle | bytes=$sz | sha256=$hash | kept=$count"
