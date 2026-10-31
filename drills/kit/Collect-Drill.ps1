<#
.SYNOPSIS
  Bring a drill's receipt and logs back into the repo, then remove the stage.

.DESCRIPTION
  Copies <stage_dir>\out\<ver>.json to drills\<ver>.json and the logs to
  drills\logs\, validates the receipt with the house lock when it is there
  (tools\release-gate.mjs --validate), and removes stage_dir (pass -Keep to
  leave it). Run from the developer's account. Generic: no app name lives here.
#>
param(
  [Parameter(Mandatory = $true)][string]$Manifest,
  [Parameter(Mandatory = $true)][string]$ToVersion,
  [switch]$Keep
)
$ErrorActionPreference = 'Stop'
$ManifestPath = (Resolve-Path -LiteralPath $Manifest).ProviderPath
$M = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$stage = [string]$M.stage_dir
$out = Join-Path $stage 'out'
$drills = Split-Path -Parent $ManifestPath
$repo = Split-Path -Parent $drills
$receipt = Join-Path $out "$ToVersion.json"
if (-not (Test-Path -LiteralPath $receipt)) {
  $why = $(if (Test-Path -LiteralPath (Join-Path $out 'run.transcript.txt')) { "see $out\run.transcript.txt" } else { 'the drill has not run' })
  throw "no receipt at $receipt - $why"
}
New-Item -ItemType Directory -Path (Join-Path $drills 'logs') -Force | Out-Null
Copy-Item -LiteralPath $receipt -Destination (Join-Path $drills "$ToVersion.json") -Force
# every log the run wrote for this version, the FROM's own diagnostics (<ver>.from-*) included
foreach ($p in @(Get-ChildItem -LiteralPath (Join-Path $out 'logs') -File -Filter "$ToVersion.*" -ErrorAction SilentlyContinue)) {
  Copy-Item -LiteralPath $p.FullName -Destination (Join-Path $drills "logs\$($p.Name)") -Force
}
$t = Join-Path $out 'run.transcript.txt'
if (Test-Path -LiteralPath $t) { Copy-Item -LiteralPath $t -Destination (Join-Path $drills "logs\$ToVersion.transcript.txt") -Force }
$code = $(if (Test-Path -LiteralPath (Join-Path $out 'exit-code.txt')) { (Get-Content -LiteralPath (Join-Path $out 'exit-code.txt') -Raw).Trim() } else { '?' })
Write-Host "collected drills\$ToVersion.json (drill exit code $code)"

# A collected file that git ignores never reaches another checkout, and the
# lock refuses a receipt whose drill_log is not in the repo. A repo-wide
# '*.log' rule did exactly that (2026-10-31): say so here, not at release.
$hidden = @()
if ((Test-Path -LiteralPath (Join-Path $repo '.git')) -and (Get-Command git -ErrorAction SilentlyContinue)) {
  Push-Location $repo
  try {
    $rels = @("drills/$ToVersion.json") + @(Get-ChildItem -LiteralPath (Join-Path $drills 'logs') -File -Filter "$ToVersion.*" | ForEach-Object { "drills/logs/$($_.Name)" })
    foreach ($r in $rels) { & git check-ignore -q --no-index -- $r; if ($LASTEXITCODE -eq 0) { $hidden += $r } }
  } finally { Pop-Location }
  if ($hidden.Count) { Write-Host "IGNORED BY GIT (add a '!' rule to .gitignore): $($hidden -join ', ')" }
}

$gate = Join-Path $repo 'tools\release-gate.mjs'
$valid = $null
if (Test-Path -LiteralPath $gate) {
  Push-Location $repo
  try { & node $gate --validate "drills/$ToVersion.json"; $valid = $LASTEXITCODE } finally { Pop-Location }
  Write-Host "release-gate --validate exit $valid"
}
if (-not $Keep) { Remove-Item -LiteralPath $stage -Recurse -Force; Write-Host "removed $stage" }
if ($code -ne '0' -or ($null -ne $valid -and $valid -ne 0) -or $hidden.Count) { exit 1 }
exit 0
