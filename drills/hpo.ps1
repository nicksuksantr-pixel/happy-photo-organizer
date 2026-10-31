# hpo.ps1 - Happy Photo Organizer's adapter for the drill kit (drills/kit/).
#
# Everything the generic runner (kit/Invoke-Drill.ps1) must not know about HPO
# lives here and in drill.json. Dot-sourced by the runner. PowerShell 5.1,
# ASCII only. Never handles a real secret: the "API key" and the pairing token
# below are drill placeholders, staged in a folder every user can read.
#
# JSON the app owns is edited as TEXT, never round-tripped through
# ConvertTo-Json: Windows PowerShell 5.1 can turn an array into
# {"value": [...], "Count": n}, which would be the drill corrupting the data it
# is meant to prove survives.

$script:HpoDrillKey = 'DRILL-PLACEHOLDER-NOT-A-GEMINI-KEY'
$script:HpoDrillToken = ('d1' * 16)               # the shape of a real token (32 hex), not a real one
$script:HpoDrillDest = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Drill archive'   # the drill account's own
$script:HpoUserJob = 'DRILL USER JOB 0001'
$script:HpoBreadcrumbs = 'happy-photo-organizer-updater.log'   # in %TEMP%, written by every version's updater
$script:HpoBusyMarker = 'drill-open-settings'   # core/updater.DRILL_BUSY_MARKER (v1.067+)

function Get-HpoDataDir($M) { return Expand-DrillPath $M.user_data_dir }
function Get-HpoExe($M) { return Join-Path (Expand-DrillPath $M.app_dir) $M.exe_name }
function Get-HpoCatalog($M) { return Join-Path (Expand-DrillPath $M.app_dir) '_internal\data\job_catalog.json' }
function Get-HpoAuth($M) { return Join-Path (Get-HpoDataDir $M) 'auth.json' }

function Write-Utf8NoBom([string]$Path, [string]$Text) {
  $dir = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  [IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Read-Utf8([string]$Path) {
  return [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
}

function Install-FromBuild([string]$Setup, $M) {
  # The released setup, silently: its default folder (%LOCALAPPDATA%\HappyPhotoOrganizer),
  # Desktop + Start menu shortcuts, Uninstall entry, then it launches the app.
  # That is the layout the GUI setup leaves with its default boxes ticked.
  $crumbs = Join-Path $env:TEMP $script:HpoBreadcrumbs
  if (Test-Path -LiteralPath $crumbs) { Remove-Item -LiteralPath $crumbs -Force }   # route evidence starts empty
  Write-DrillLog "installing FROM: $Setup --silent"
  $p = Start-Process -FilePath $Setup -ArgumentList '--silent' -PassThru
  if (-not $p.WaitForExit(600000)) { throw 'the FROM setup did not finish in 10 minutes' }
  $exe = Get-HpoExe $M
  if (-not (Test-Path -LiteralPath $exe)) { throw "the FROM setup exited $($p.ExitCode) and $exe is not there" }
  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-AppProcesses $M.exe_name).Count -eq 0 -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
  Write-DrillLog "FROM setup exit $($p.ExitCode); app launched by it: $((Get-AppProcesses $M.exe_name).Count -gt 0)"
  # the user's data goes in with the app closed, as it would already be there
  Stop-AppProcesses $M.exe_name
}

function Set-DrillFixtures($M) {
  $data = Get-HpoDataDir $M
  New-Item -ItemType Directory -Path (Join-Path $script:HpoDrillDest '30 Drill job') -Force | Out-Null
  $destJson = $script:HpoDrillDest.Replace('\', '\\')
  # settings: placeholder key (so no Settings dialog), a pairing token, automatic checks on
  Write-Utf8NoBom (Get-HpoAuth $M) (@"
{
  "api_key": "$script:HpoDrillKey",
  "model": "gemini-3.5-flash-lite",
  "auto_check_updates": true,
  "jobshot_token": "$script:HpoDrillToken",
  "last_dest_root": "$destJson"
}
"@)
  # the phone's receipt book: one job already filed
  Write-Utf8NoBom (Join-Path $data 'jobshot_filed.json') (@"
{"version": 1, "jobs": {"J-2026-10-30-0001": {"folder": "30 Drill job", "folder_path": "$destJson\\30 Drill job", "photos": 3, "extras": [], "filed_at": "2026-10-30T12:00:00"}}}
"@)
  # a job name the user taught the app: user data that (until a later release
  # moves it, bug U8) lives INSIDE the install tree, carried by the installer's merge
  $cat = Get-HpoCatalog $M
  $raw = Read-Utf8 $cat
  $hit = [regex]::Match($raw, '"jobs"\s*:\s*\[')
  if (-not $hit.Success) { throw "the catalog $cat has no jobs list" }
  $job = '{"name": "' + $script:HpoUserJob + '", "normalized": "' + $script:HpoUserJob.ToLower() +
         '", "occurrences": 1, "ships": ["Drill"], "months_seen": [], "dates_seen": [], "variants": ["' +
         $script:HpoUserJob + '"], "keywords": ["drill", "user", "job"]}'
  $at = $hit.Index + $hit.Length
  $rest = $raw.Substring($at).TrimStart()
  $sep = $(if ($rest.StartsWith(']')) { '' } else { ',' })
  Write-Utf8NoBom $cat ($raw.Substring(0, $at) + "`n    " + $job + $sep + $raw.Substring($at))
  # a taskbar pin, as a user would have one
  foreach ($s in $M.shortcuts) {
    if ($s -like '*User Pinned*') { New-Shortcut (Expand-DrillPath $s) (Get-HpoExe $M) }
  }
  Write-DrillLog 'fixtures: auth.json (placeholder key + pairing token + destination), jobshot_filed.json (1 receipt), 1 user job in the catalog, a taskbar-pin .lnk'
}

function Get-FixtureReport($M) {
  # field by field: the app rewrites auth.json itself (window position), so
  # its bytes may change; what the user set in it must not
  $r = [ordered]@{}
  $auth = $null
  try { $auth = (Read-Utf8 (Get-HpoAuth $M)) | ConvertFrom-Json } catch {}
  foreach ($k in @('api_key', 'model', 'auto_check_updates', 'jobshot_token', 'last_dest_root')) {
    $v = '(no auth.json)'
    if ($auth) { $v = $(if ($auth.PSObject.Properties.Name -contains $k) { [string]$auth.$k } else { '(missing)' }) }
    if ($k -in @('api_key', 'jobshot_token') -and $v -notlike '(*') { $v = 'sha256:' + (Get-StringSha $v).Substring(0, 12) }
    $r["auth.$k"] = $v
  }
  $jobs = @()
  try { $jobs = @(((Read-Utf8 (Get-HpoCatalog $M)) | ConvertFrom-Json).jobs) } catch {}
  $r['catalog.user_job'] = @($jobs | Where-Object { $_.name -eq $script:HpoUserJob }).Count
  return $r
}

function Get-StringSha([string]$s) {
  $h = [Security.Cryptography.SHA256]::Create()
  try { return (($h.ComputeHash([Text.Encoding]::UTF8.GetBytes($s)) | ForEach-Object { $_.ToString('x2') }) -join '') }
  finally { $h.Dispose() }
}

function Get-LayoutDescription($M, [string[]]$Shortcuts) {
  return ("v{0} installed by its own released setup (--silent: the default folder {1}, the layout the GUI setup leaves " +
          "with its default boxes ticked), as standard user '{2}'; shortcuts: {3}") -f $M.from.version,
          (Expand-DrillPath $M.install_dir), $env:USERNAME, ($Shortcuts -join '; ')
}

function Start-TheApp($M) {
  Start-Process -FilePath (Get-HpoExe $M) | Out-Null
}

function Invoke-FreshInstall([string]$Setup, [string]$Into, $M) {
  # the candidate's own setup lays out a fresh install with no shortcuts,
  # registry or launch (installer --fresh-into, refused outside a drill)
  $p = Start-Process -FilePath $Setup -ArgumentList @('--fresh-into', ('"' + $Into + '"')) -PassThru
  if (-not $p.WaitForExit(600000)) { return $false }
  Write-DrillLog "fresh install of the candidate into $Into exited $($p.ExitCode)"
  return ($p.ExitCode -eq 0)
}

function Get-FromDiagnostics($M) {
  # the FROM build's updater breadcrumbs: why it did or did not fetch, download, hand over.
  # Reset deletes them, and Nick's account cannot read %TEMP% here (run 1, R7).
  return @(Join-Path $env:TEMP $script:HpoBreadcrumbs)
}

function Get-FromRouteEvidence($M) {
  # The FROM build's own updater breadcrumbs in %TEMP% (every version writes
  # them). Evidence only if it asked the route itself and THEN fetched from
  # it, in that order; nothing earlier in the file counts.
  #   repo-env (FROM v1.065, no drill feed): the public test repo drill_repo.
  #   feed (FROM v1.066+): the kit's loopback feed. In drill mode v1.066 reads
  #     HAPPY_UPDATE_FEED for every check (core/updater.feed_url), so its
  #     breadcrumbs name 127.0.0.1, never the test repo (review 2026-10-31:
  #     with only the repo-env patterns, real_update_path would always fail).
  $f = Join-Path $env:TEMP $script:HpoBreadcrumbs
  if (-not (Test-Path -LiteralPath $f)) { return @() }
  $lines = @(Get-Content -LiteralPath $f -Encoding UTF8)
  if ([string]$M.from_route.kind -eq 'repo-env') {
    $askLike = '*/repos/' + $M.drill_repo + '/releases/latest*'
    $getLike = '*download_installer start*' + $M.drill_repo + '/releases/download/*'
  } else {
    $askLike = '*_fetch_latest_release: GET http://127.0.0.1:*/latest*'
    $getLike = '*download_installer start: url=http://127.0.0.1:*/asset/*'
  }
  $ask = -1; $get = -1; $ok = -1
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $l = $lines[$i]
    if ($ask -lt 0 -and $l -like $askLike) { $ask = $i }
    elseif ($ask -ge 0 -and $get -lt 0 -and $l -like $getLike) { $get = $i }
    elseif ($get -ge 0 -and $ok -lt 0 -and $l -like '*: SUCCESS*') { $ok = $i }
  }
  if ($get -lt 0) { return @() }
  return @(@($ask, $get, $ok) | Where-Object { $_ -ge 0 } | ForEach-Object { $lines[$_] })
}

function Set-AppBusy($M) {
  # busy the way a user makes it busy: a dialog open. The kit calls this on the
  # candidate (TO). Up to v1.066 the step held the API key back so the app
  # opened Settings by itself; from v1.067 a built-in key wins and it never
  # does. So the step drops the drill marker instead: the next start in drill
  # mode opens Settings once and deletes it (core/updater.take_drill_busy_marker).
  Stop-AppProcesses $M.exe_name
  $marker = Join-Path (Get-HpoDataDir $M) $script:HpoBusyMarker
  Write-Utf8NoBom $marker 'drill: open Settings once at the next start'
}

function Clear-AppBusy($M) {
  $deadline = (Get-Date).AddSeconds(10)
  while (-not (Test-WindowOpen $M.busy_window_prefix) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }
  $n = Close-WindowByTitlePrefix $M.busy_window_prefix
  Write-DrillLog "closed $n '$($M.busy_window_prefix)...' window(s): the app is idle now"
}

function Restore-AfterBusy($M) {
  Stop-AppProcesses $M.exe_name
  $marker = Join-Path (Get-HpoDataDir $M) $script:HpoBusyMarker
  if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker -Force }   # never consumed: leave nothing behind
}

function Get-EmbeddedKeyEvidence($M) {
  # KEY_EMBED 7 (embedded_key_works): one real Gemini call from the UPDATED
  # build with its built-in key. The app makes the call itself and writes the
  # result - status, model, the key's sha256 fingerprint, never the key - then
  # exits (--check-embedded-key, drill mode only, no window, beside the app).
  # Returns: result ('pass'/'fail'), evidence (one line), fp, app, status, model.
  $out = Join-Path (Get-HpoDataDir $M) 'logs\embedded-key-check.json'
  if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Force }
  $p = Start-Process -FilePath (Get-HpoExe $M) -ArgumentList '--check-embedded-key' -PassThru
  if (-not $p.WaitForExit(120000)) {
    try { $p.Kill() } catch {}
    return [ordered]@{ result = 'fail'; evidence = 'no result within 120 s'; fp = ''; app = ''; status = ''; model = '' }
  }
  $r = $null
  try { $r = (Read-Utf8 $out) | ConvertFrom-Json } catch {}
  if (-not $r) {
    return [ordered]@{ result = 'fail'; evidence = "exit $($p.ExitCode), no $out"; fp = ''; app = ''; status = ''; model = '' }
  }
  $ok = ($p.ExitCode -eq 0 -and [string]$r.status -eq '200' -and [string]$r.model -and [string]$r.fp)
  $ev = "exit $($p.ExitCode); status $($r.status); model $($r.model); key fp sha256:$(([string]$r.fp).Substring(0, [Math]::Min(12, ([string]$r.fp).Length)))" +
        $(if ($r.error) { "; error: $($r.error)" } else { '' })
  return [ordered]@{ result = $(if ($ok) { 'pass' } else { 'fail' }); evidence = $ev; fp = [string]$r.fp
                     app = [string]$r.app; status = [string]$r.status; model = [string]$r.model }
}

function Reset-DrillAccount($M) {
  # only ever inside a drill account: this removes the app and its data
  if ($env:USERNAME -notlike $M.drill_user_like) {
    throw "refusing to reset: user '$env:USERNAME' is not a drill account ($($M.drill_user_like))"
  }
  Stop-AppProcesses $M.exe_name
  foreach ($g in $M.install_glob) {
    Get-ChildItem -Path (Expand-DrillPath $g) -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
  }
  foreach ($s in $M.shortcuts) {
    $p = Expand-DrillPath $s
    foreach ($q in @($p, [IO.Path]::ChangeExtension($p, '.bat'))) { if (Test-Path -LiteralPath $q) { Remove-Item -LiteralPath $q -Force } }
  }
  $k = 'HKCU:\' + $M.uninstall_key
  if (Test-Path $k) { Remove-Item $k -Recurse -Force }
  $d = Get-HpoDataDir $M
  if (Test-Path -LiteralPath $d) { Remove-Item -LiteralPath $d -Recurse -Force }
  if (Test-Path -LiteralPath $script:HpoDrillDest) { Remove-Item -LiteralPath $script:HpoDrillDest -Recurse -Force }
  $f = Join-Path $env:TEMP $script:HpoBreadcrumbs
  foreach ($q in @($f, "$f.1")) { if (Test-Path -LiteralPath $q) { Remove-Item -LiteralPath $q -Force } }
  Get-ChildItem -LiteralPath $env:LOCALAPPDATA -Filter 'drill-marker-*.txt' -ErrorAction SilentlyContinue | Remove-Item -Force
  Write-Host "reset: $($M.app) removed from '$env:USERNAME'"
}
