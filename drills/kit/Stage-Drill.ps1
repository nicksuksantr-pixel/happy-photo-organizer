<#
.SYNOPSIS
  Stage a drill where the drill account can read it (UPDATE_DRILL section 5.2).

.DESCRIPTION
  The drill account cannot read the developer's profile, so everything the run
  needs is copied into the manifest's stage_dir (e.g. C:\Users\Public\<App>-drill):
  the kit, the manifest and its adapter, the FROM and TO release files. It
  writes run.ps1 (what the drill account runs, after Switch user) and reset.ps1.

  Every user on the PC can read stage_dir, so it refuses to stage anything that
  looks like a key or a token. Generic: no app name lives here.

.EXAMPLE
  .\kit\Stage-Drill.ps1 -Manifest .\drill.json -FromSetup <previous release file> -ToSetup <candidate> -ToVersion 1.066
#>
param(
  [Parameter(Mandatory = $true)][string]$Manifest,
  [Parameter(Mandatory = $true)][string]$FromSetup,
  [Parameter(Mandatory = $true)][string]$ToSetup,
  [Parameter(Mandatory = $true)][string]$ToVersion,
  [string]$NextVersion = ''
)
$ErrorActionPreference = 'Stop'
$ManifestPath = (Resolve-Path -LiteralPath $Manifest).ProviderPath
$M = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$stage = [string]$M.stage_dir
if (-not $stage -or $stage -notlike 'C:\Users\Public\*') { throw "stage_dir must be under C:\Users\Public: '$stage'" }
foreach ($f in @($FromSetup, $ToSetup)) { if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { throw "not a file: $f" } }

$src = Split-Path -Parent $ManifestPath
$texts = @($ManifestPath, (Join-Path $src $M.adapter)) + @(Get-ChildItem -LiteralPath $PSScriptRoot -File | ForEach-Object { $_.FullName })
$secret = 'AIza[0-9A-Za-z_\-]{30,}|ghp_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{30,}|sk-[A-Za-z0-9\-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY'
foreach ($t in $texts) {
  if (Select-String -LiteralPath $t -Pattern $secret -Quiet) { throw "refusing to stage: $t contains something that looks like a key or token" }
}

if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
foreach ($d in @('kit', 'from', 'to', 'out')) { New-Item -ItemType Directory -Path (Join-Path $stage $d) -Force | Out-Null }
Copy-Item -Path (Join-Path $PSScriptRoot '*') -Destination (Join-Path $stage 'kit') -Recurse
Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $stage 'drill.json')
Copy-Item -LiteralPath (Join-Path $src $M.adapter) -Destination (Join-Path $stage $M.adapter)
$asset = [string]$M.asset_name
Copy-Item -LiteralPath $FromSetup -Destination (Join-Path $stage "from\$asset")
Copy-Item -LiteralPath $ToSetup -Destination (Join-Path $stage "to\$asset")

$next = $(if ($NextVersion) { " -NextVersion '$NextVersion'" } else { '' })
$run = @"
# written by Stage-Drill.ps1 - run AS THE DRILL ACCOUNT, outside the Claude app
`$here = `$PSScriptRoot
Start-Transcript -LiteralPath (Join-Path `$here 'out\run.transcript.txt') -Force | Out-Null
& (Join-Path `$here 'kit\Invoke-Drill.ps1') -Manifest (Join-Path `$here 'drill.json') ``
  -FromSetup (Join-Path `$here 'from\$asset') -ToSetup (Join-Path `$here 'to\$asset') ``
  -ToVersion '$ToVersion' -OutDir (Join-Path `$here 'out')$next
`$code = `$LASTEXITCODE
Set-Content -LiteralPath (Join-Path `$here 'out\exit-code.txt') -Value `$code
Stop-Transcript | Out-Null
exit `$code
"@
$reset = @"
# written by Stage-Drill.ps1 - removes what a drill installed, from the DRILL account only
& (Join-Path `$PSScriptRoot 'kit\Invoke-Drill.ps1') -Manifest (Join-Path `$PSScriptRoot 'drill.json') -FromSetup x -ToSetup x -ToVersion x -OutDir (Join-Path `$PSScriptRoot 'out') -Reset
"@
Set-Content -LiteralPath (Join-Path $stage 'run.ps1') -Value $run -Encoding ASCII
Set-Content -LiteralPath (Join-Path $stage 'reset.ps1') -Value $reset -Encoding ASCII

$fromSha = (Get-FileHash -LiteralPath $FromSetup -Algorithm SHA256).Hash.ToLower()
$toSha = (Get-FileHash -LiteralPath $ToSetup -Algorithm SHA256).Hash.ToLower()
Write-Host "staged in $stage"
Write-Host "  FROM v$($M.from.version) sha256 $fromSha $(if ($fromSha -eq ([string]$M.from.sha256).ToLower()) { '(the released file)' } else { '(NOT the released file - the drill will refuse it)' })"
Write-Host "  TO   v$ToVersion sha256 $toSha"
Write-Host "next: as the drill account, run $stage\reset.ps1 then $stage\run.ps1 (Switch user to it; never runas)"
