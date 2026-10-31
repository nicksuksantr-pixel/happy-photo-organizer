<#
.SYNOPSIS
  Run an update drill and write its receipt (UPDATE_DRILL section 5, 5a, 6).

.DESCRIPTION
  Generic runner. Everything about the app comes from the project's manifest
  (drills/drill.json) and the adapter script it names, which must define:

    Install-FromBuild   -Setup <path> -M <manifest>   install the PREVIOUS release the way users have it; leave the app closed
    Set-DrillFixtures   -M <manifest>                  write user data to prove survives (no real secrets)
    Get-FixtureReport   -M <manifest>                  field-by-field facts about that data (a hashtable)
    Start-TheApp        -M <manifest>                  start the installed app (it inherits this process's environment)
    Invoke-FreshInstall -Setup <path> -Into <dir> -M   install the candidate into an empty folder, as a fresh install would
    Get-FromRouteEvidence -M <manifest>                lines showing the OLD build's own updater did the fetching
    Set-AppBusy / Clear-AppBusy / Restore-AfterBusy -M make the app busy the way a user would, and undo it
    Reset-DrillAccount  -M <manifest>                  remove everything a drill installed (refuses outside a drill account)
  and may define:
    Get-FromDiagnostics -M <manifest>                  files the OLD build writes about its own update (only the drill
                                                       account can read them): quoted in the progress lines while the
                                                       update is awaited, copied to <OutDir>\logs\<ver>.from-<name>

  Run it OUTSIDE the Claude app (its shell virtualises %LOCALAPPDATA%), as a
  standard (not admin) Windows user made for drills, from a folder that user
  can read. It never needs a secret, and must never be given one.

  Exit code 0 only when every required check passed.
#>
param(
  [Parameter(Mandatory = $true)][string]$Manifest,
  [Parameter(Mandatory = $true)][string]$FromSetup,
  [Parameter(Mandatory = $true)][string]$ToSetup,
  [Parameter(Mandatory = $true)][string]$ToVersion,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [string]$NextVersion = '',
  [switch]$Reset
)

$ErrorActionPreference = 'Stop'
$kit = $PSScriptRoot
Import-Module (Join-Path $kit 'DrillKit.psm1') -Force
$ManifestPath = (Resolve-Path -LiteralPath $Manifest).ProviderPath
$M = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
. (Join-Path (Split-Path -Parent $ManifestPath) $M.adapter)

if ($Reset) { Reset-DrillAccount -M $M; exit 0 }

if (-not $NextVersion) {
  $parts = $ToVersion.Split('.')
  $last = $parts[$parts.Length - 1]
  $parts[$parts.Length - 1] = ([int]$last + 1).ToString().PadLeft($last.Length, '0')
  $NextVersion = $parts -join '.'
}

New-Item -ItemType Directory -Path (Join-Path $OutDir 'logs') -Force | Out-Null
$drillLog = Join-Path $OutDir "logs\$ToVersion.log"
Start-DrillLog $drillLog
$checks = [ordered]@{}
$extra = [ordered]@{}
# KEY_EMBED 6 (2026-10-31): an app that builds a Gemini key in says so in drill.json; the receipt must then carry the
# key's fingerprint and the proof that the UPDATED build can use it (HPO's adapter: Get-EmbeddedKeyEvidence)
$embedsKey = (($M.PSObject.Properties.Name -contains 'embeds_key') -and [bool]$M.embeds_key)
$embeddedKey = $null
$ulog = Expand-DrillPath $M.update_log
$exeName = [string]$M.exe_name
$appDir = Expand-DrillPath $M.app_dir
$exe = Join-Path $appDir $exeName
$installDir = Expand-DrillPath $M.install_dir
$port = [int]$M.feed.port
$feedState = Join-Path $OutDir 'feed-state.json'
$feedAccess = Join-Path $OutDir "logs\$ToVersion.feed.jsonl"
$feedProc = $null
$lock = $null
$diagFiles = @()     # the adapter's optional Get-FromDiagnostics: files only the drill account can read
$T = $M.timeouts

function Check([string]$Id, [bool]$Pass, [string]$Evidence) {
  $r = 'fail'; if ($Pass) { $r = 'pass' }
  $checks[$Id] = New-Check $r $Evidence
  Write-DrillLog ("CHECK {0} {1} :: {2}" -f $Id, $r.ToUpper(), $Evidence)
}

function Lines-Since([int]$After) { return @(Read-UpdateLog $ulog | Where-Object { $_.N -gt $After }) }

function Restart-App {
  Stop-AppProcesses $exeName
  $mark = Get-LogLineCount $ulog
  Start-TheApp -M $M
  return $mark
}

function Feed-Release([string]$Version, [string]$Fault, [string]$Mode) {
  $rel = New-FeedRelease -Tag "v$Version" -AssetName $M.asset_name -AssetFile $ToSetup -DigestSha $toSha -Port $port
  Set-FeedState $feedState ([ordered]@{
    mode = $Mode; release = $rel
    assets = [ordered]@{ ($M.asset_name) = [ordered]@{ file = $ToSetup; fault = $Fault } }
  })
}

try {
  # ---- 0. preflight ------------------------------------------------------
  $who = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  Write-DrillLog "drill of $($M.app) $($M.from.version) -> $ToVersion as $who on $env:COMPUTERNAME"
  # a drill installs, kills and deletes the app: never in a real user's account
  if (-not $M.drill_user_like -or $env:USERNAME -notlike $M.drill_user_like) {
    throw "not a drill account: '$env:USERNAME' does not match the manifest's drill_user_like '$($M.drill_user_like)'"
  }
  if (Test-IsAdmin) { throw 'running as an administrator: a drill runs as a STANDARD user (a UAC prompt is a fail)' }
  $lockWait = $(if ($T.PSObject.Properties.Name -contains 'lock_wait_s') { [int]$T.lock_wait_s } else { 3600 })
  $lock = Enter-DrillLock ([string]$M.app) $lockWait
  $fromSha = Get-Sha256 $FromSetup
  $toSha = Get-Sha256 $ToSetup
  Write-DrillLog "FROM $FromSetup sha256=$fromSha"
  Write-DrillLog "TO   $ToSetup sha256=$toSha"
  if ($fromSha -ne ([string]$M.from.sha256).ToLower()) {
    throw "FROM is not the released file: sha256 $fromSha, the manifest's release is $($M.from.sha256)"
  }
  # measured here, where it is checked: a drill that stops later must not report it as not measured (R7)
  Check 'start_from_released_build' $true ("FROM = $FromSetup, sha256 $fromSha = the released v$($M.from.version) file named in drills/drill.json")
  foreach ($g in $M.install_glob) {
    $hits = @(Get-ChildItem -Path (Expand-DrillPath $g) -Directory -ErrorAction SilentlyContinue)
    if ($hits.Count) { throw "not a clean account: $($hits[0].FullName) exists. Run with -Reset first." }
  }
  if (Test-Path -LiteralPath (Expand-DrillPath $M.user_data_dir)) {
    throw "not a clean account: $(Expand-DrillPath $M.user_data_dir) exists. Run with -Reset first."
  }
  $marker = Join-Path $env:LOCALAPPDATA ("drill-marker-{0}.txt" -f [guid]::NewGuid().ToString('N').Substring(0, 8))
  Set-Content -LiteralPath $marker -Value "written by the drill harness at $((Get-Date).ToString('o'))"
  Write-DrillLog "MSIX sanity marker: $marker (confirm it from a second, unpackaged shell)"

  # ---- 1. FROM, installed the way users have it, with user data ----------
  Install-FromBuild -Setup $FromSetup -M $M
  Set-DrillFixtures -M $M
  $sentinels = [ordered]@{}
  foreach ($s in $M.sentinels) {
    $p = Join-Path (Expand-DrillPath $M.user_data_dir) $s
    $sentinels[$s] = $(if (Test-Path -LiteralPath $p) { Get-Sha256 $p } else { 'absent' })
  }
  $shortcutsBefore = [ordered]@{}
  foreach ($s in $M.shortcuts) {
    $p = Expand-DrillPath $s
    if (Test-Path -LiteralPath $p) { $shortcutsBefore[$p] = Resolve-Shortcut $p }
  }
  $fixturesBefore = Get-FixtureReport -M $M
  $treeBefore = Get-TreeHashes $installDir
  Write-DrillLog ("FROM installed: {0} files under {1}" -f $treeBefore.Count, $installDir)
  foreach ($k in $sentinels.Keys) { Write-DrillLog "  data $k sha256=$($sentinels[$k])" }
  foreach ($k in $shortcutsBefore.Keys) { Write-DrillLog "  shortcut $k -> $($shortcutsBefore[$k])" }
  foreach ($k in $fixturesBefore.Keys) { Write-DrillLog "  fixture $k = $($fixturesBefore[$k])" }
  $layout = Get-LayoutDescription -M $M -Shortcuts @($shortcutsBefore.Keys)

  # ---- 2. the update, through FROM's own path ----------------------------
  $feedProc = Start-FakeFeed $kit $port $feedState $feedAccess
  Feed-Release $ToVersion 'none' 'serve'          # what TO sees once it runs: itself
  [Environment]::SetEnvironmentVariable($M.feed.drill_env, '1', 'Process')
  [Environment]::SetEnvironmentVariable($M.feed.feed_env, "http://127.0.0.1:$port/latest", 'Process')
  $route = [string]$M.from_route.kind
  if ($route -eq 'repo-env') {
    [Environment]::SetEnvironmentVariable($M.from_route.env, $M.drill_repo, 'Process')
    Write-DrillLog "route: FROM's own updater, pointed by $($M.from_route.env) at the public test repo $($M.drill_repo)"
  } else {
    Feed-Release $ToVersion 'none' 'serve'
    Write-DrillLog "route: FROM's own updater, through the loopback feed"
  }
  $mark = Get-LogLineCount $ulog
  $t0 = Get-Date
  if (Get-Command Get-FromDiagnostics -ErrorAction SilentlyContinue) { $diagFiles = @(Get-FromDiagnostics -M $M) }
  Start-TheApp -M $M
  Write-DrillLog "started FROM; the harness starts nothing else until the checks"
  # Never silent, never waiting on a lost cause (R7, run 1 sat 27 min mute after a terminal FAILED):
  # every minute a line with what update.log and the FROM's own diagnostics say; a FAILED for TO
  # ends the wait 2 minutes later (long enough for a recovery that logs FAILED and goes on).
  $waitProgress = {
    param($s)
    $new = @(Lines-Since $mark)
    $last = $(if ($new.Count) { $new[-1].Line } else { '-' })
    $from = @($diagFiles | ForEach-Object { Get-LastLine $_ } | Where-Object { $_ })
    Write-DrillLog ("  waiting for v{0} to start: {1} s; update.log +{2} line(s), last: {3}{4}" -f $ToVersion, $s,
      $new.Count, $last, $(if ($from.Count) { "; FROM says: $($from[-1])" } else { '' }))
  }
  $started = Wait-ForLogLine -Path $ulog -AfterLine $mark -TimeoutSec ([int]$T.update_s) `
    -Match { param($e) $e.Kind -eq 'STARTED' -and $e.Version -eq $ToVersion } `
    -GiveUp { param($e) $e.Kind -eq 'UPDATE' -and $e.Stage -eq 'FAILED' -and $e.Version -eq $ToVersion } `
    -Progress $waitProgress
  $since = Lines-Since $mark
  foreach ($e in $since) { Write-DrillLog "  update.log: $($e.Line)" }
  $swapped = @($since | Where-Object { $_.Stage -eq 'SWAPPED' -and $_.Version -eq $ToVersion })
  $routeEvidence = Get-FromRouteEvidence -M $M
  foreach ($l in $routeEvidence) { Write-DrillLog "  route evidence: $l" }
  Check 'real_update_path' ([bool]($started -and $swapped.Count -eq 1 -and $routeEvidence.Count -gt 0)) (
    "the harness started only the FROM v$($M.from.version) exe; its own updater fetched: " + ($routeEvidence -join ' | ') +
    "; then the TO installer: " + (($swapped | ForEach-Object { $_.Line }) -join ' | '))
  if (-not $started) { throw "TO never started within $($T.update_s) s - see the update log lines above" }
  Check 'new_version_running' ($started.Version -eq $ToVersion) $started.Line

  # ---- 3. after the cleanup window: measure --------------------------------
  $cleaned = Wait-ForLogLine $ulog $mark { param($e) $e.Stage -eq 'CLEANED' -and $e.Version -eq $ToVersion } ([int]$T.cleanup_s)
  $procs = Get-AppProcesses $exeName
  Check 'one_process' ($procs.Count -eq 1 -and $procs[0].Path -ieq $exe) (
    "{0} process(es): {1}" -f $procs.Count, (($procs | ForEach-Object { "$($_.Id) $($_.Path)" }) -join '; '))
  Check 'relaunched_itself' ([bool]($started -and $procs.Count -eq 1 -and $procs[0].Path -ieq $exe)) (
    "the harness started nothing after FROM; '$($started.Line)' and pid $(@($procs | ForEach-Object { $_.Id }) -join ',') runs $exe with its window (" + $M.relaunch + ")")

  $folders = @()
  foreach ($g in $M.install_glob) { $folders += @(Get-ChildItem -Path (Expand-DrillPath $g) -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }) }
  $exes = @(Get-ChildItem -LiteralPath $installDir -Recurse -File -Force -Filter $exeName -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
  $updateLeft = Test-Path -LiteralPath (Join-Path $installDir '.update')
  $regHKCU = Test-Path ("HKCU:\" + $M.uninstall_key)
  $regHKLM = Test-Path ("HKLM:\" + $M.uninstall_key)
  Check 'one_install' ($folders.Count -eq 1 -and $exes.Count -eq 1 -and -not $updateLeft -and $regHKCU -and -not $regHKLM) (
    "install folders: $($folders -join ', '); exe copies: $($exes -join ', '); .update left after cleanup: $updateLeft" +
    " (CLEANED line: $(if ($cleaned) { $cleaned.Line } else { 'none' })); Uninstall entry HKCU=$regHKCU HKLM=$regHKLM")

  $ref = Join-Path $OutDir "fresh-$ToVersion"
  if (Test-Path -LiteralPath $ref) { Remove-Item -LiteralPath $ref -Recurse -Force }
  $freshOk = Invoke-FreshInstall -Setup $ToSetup -Into $ref -M $M
  $treeAfter = Get-TreeHashes $installDir
  $treeRef = Get-TreeHashes $ref
  $allow = @($M.tree_allowlist)
  $diffs = Compare-Trees $treeAfter $treeRef $allow
  Check 'tree_matches_fresh_install' ($freshOk -and $treeRef.Count -gt 0 -and $diffs.Count -eq 0) (
    "updated {0} files vs a fresh install of v{1} {2} files, allowlist [{3}]: {4}" -f $treeAfter.Count, $ToVersion, $treeRef.Count,
    ($allow -join ', '), $(if ($diffs.Count) { ($diffs | Select-Object -First 20) -join '; ' } else { 'identical' }))

  $exeSha = Get-Sha256 $exe
  $refExe = $treeRef[(([string]$M.app_dir_rel) + '/' + $exeName)]
  $scLines = @(); $scOk = $shortcutsBefore.Count -gt 0
  foreach ($p in $shortcutsBefore.Keys) {
    $now = Resolve-Shortcut $p
    $ok = ($now -ieq $exe)
    if (-not $ok) { $scOk = $false }
    $scLines += "$p -> $now ($(if ($ok) { 'the updated exe' } else { 'NOT the updated exe' }))"
  }
  Check 'shortcuts_open_new' ($scOk -and $exeSha -eq $refExe) (($scLines -join '; ') + "; that exe sha256 $exeSha = fresh v$ToVersion exe: $($exeSha -eq $refExe); it ran as: $($started.Line)")

  $dataLines = @(); $dataOk = $true
  foreach ($s in $sentinels.Keys) {
    $p = Join-Path (Expand-DrillPath $M.user_data_dir) $s
    $now = $(if (Test-Path -LiteralPath $p) { Get-Sha256 $p } else { 'absent' })
    if ($now -ne $sentinels[$s]) { $dataOk = $false }
    $dataLines += "$s $(if ($now -eq $sentinels[$s]) { 'byte-identical' } else { "CHANGED $($sentinels[$s]) -> $now" })"
  }
  $fixturesAfter = Get-FixtureReport -M $M
  foreach ($k in $fixturesBefore.Keys) {
    if ([string]$fixturesAfter[$k] -ne [string]$fixturesBefore[$k]) { $dataOk = $false }
    $dataLines += "$k before=$($fixturesBefore[$k]) after=$($fixturesAfter[$k])"
  }
  Check 'user_data_intact' $dataOk ($dataLines -join '; ')

  $sinceStart = @(Read-UpdateLog $ulog | Where-Object { $_.N -gt $started.N })
  $noNewer = @($sinceStart | Where-Object { $_.Stage -eq 'CHECK' -and $_.Version -eq $ToVersion -and $_.Detail -like 'nothing newer*' })
  $offered = @($sinceStart | Where-Object { $_.Stage -in @('FOUND', 'DOWNLOADED', 'HANDOVER') })
  $fetched = @(Read-AccessLog $feedAccess | Where-Object { ($_.PSObject.Properties.Name -contains 'path') -and $_.path -like '/asset/*' })
  Check 'no_update_loop' ($noNewer.Count -ge 1 -and $offered.Count -eq 0 -and $fetched.Count -eq 0) (
    "fed v$ToVersion itself: " + $(if ($noNewer.Count) { $noNewer[0].Line } else { 'no CHECK line' }) +
    "; FOUND/DOWNLOADED/HANDOVER since: $($offered.Count); asset requests at the feed: $($fetched.Count)")

  # ---- KEY_EMBED 6: the built-in key works from the UPDATED build -----------
  # TO is up and the drill environment is set; the adapter runs the installed exe's own self-check and returns
  # result / evidence / fp / repo. A key that never reached the shipped bytes, or that Google refuses, fails here.
  if ($embedsKey) {
    if (Get-Command Get-EmbeddedKeyEvidence -ErrorAction SilentlyContinue) {
      $ek = Get-EmbeddedKeyEvidence -M $M
      if ([string]$ek.fp) { $embeddedKey = [ordered]@{ fp = [string]$ek.fp; repo = [string]$ek.repo } }
      Check 'embedded_key_works' ([string]$ek.result -eq 'pass') ([string]$ek.evidence)
    } else {
      Check 'embedded_key_works' $false 'drill.json says embeds_key, but the adapter defines no Get-EmbeddedKeyEvidence'
    }
  }

  # ---- 4. failure injection, on TO through the loopback feed --------------
  $unknown = @()
  $unknownOk = $true
  foreach ($mode in @('500', '403', 'drop')) {
    Feed-Release $ToVersion 'none' $mode
    $mk = Restart-App
    $e = Wait-ForLogLine $ulog $mk { param($x) $x.Stage -eq 'CHECK' -and $x.Version -eq $ToVersion } ([int]$T.start_s)
    $said = $(if ($e) { $e.Line } else { 'no CHECK line' })
    if (-not $e -or $e.Detail -notlike 'could not check*') { $unknownOk = $false }
    $unknown += "feed $mode -> $said"
  }
  Check 'unknown_is_not_no' $unknownOk ($unknown -join '; ')

  Feed-Release $NextVersion 'flip' 'serve'
  $mk = Restart-App
  $ref1 = Wait-ForLogLine $ulog $mk { param($x) $x.Stage -eq 'REFUSED' -and $x.Version -eq $NextVersion } ([int]$T.update_s)
  Start-Sleep -Seconds 10
  $ho = @(Lines-Since $mk | Where-Object { $_.Stage -eq 'HANDOVER' })
  $procs = Get-AppProcesses $exeName
  Check 'bad_download_refused' ([bool]($ref1 -and $ho.Count -eq 0 -and $procs.Count -eq 1)) (
    "fed v$NextVersion with one byte flipped: " + $(if ($ref1) { $ref1.Line } else { 'no REFUSED line' }) +
    "; HANDOVER lines: $($ho.Count); v$ToVersion still running: $($procs.Count -eq 1)")

  # sees N+1 - with the app ALREADY busy, so it must wait, then install once idle.
  # Busy first, N+1 second (H8, HPO run 2): with N+1 already on the feed at start, the app
  # found it, fetched it from loopback in a second and handed over 2 s after starting, before
  # its busy window was even open. Now it comes up busy with nothing newer on the feed, and
  # finds N+1 at its next periodic check - minutes, so that wait is update_s, with progress.
  Set-AppBusy -M $M
  Feed-Release $ToVersion 'none' 'serve'
  $mk = Restart-App
  $busyBy = (Get-Date).AddSeconds([int]$T.start_s)
  while (-not (Test-WindowOpen $M.busy_window_prefix) -and (Get-Date) -lt $busyBy) { Start-Sleep -Milliseconds 300 }
  if (-not (Test-WindowOpen $M.busy_window_prefix)) {
    throw "could not make the app busy: no '$($M.busy_window_prefix)...' window within $($T.start_s) s"
  }
  Write-DrillLog "the app is busy ($($M.busy_description)); now feeding v$NextVersion"
  Feed-Release $NextVersion 'none' 'serve'
  $found = Wait-ForLogLine -Path $ulog -AfterLine $mk -TimeoutSec ([int]$T.update_s) `
    -Match { param($x) $x.Stage -eq 'FOUND' -and $x.Version -eq $NextVersion } `
    -Progress { param($s) Write-DrillLog "  waiting for the app's next check to find v${NextVersion}: $s s" }
  $verified = Wait-ForLogLine $ulog $mk { param($x) $x.Stage -eq 'VERIFIED' -and $x.Version -eq $NextVersion } ([int]$T.update_s)
  Check 'sees_next_release' ([bool]$found) ("fed a fake v${NextVersion}: " + $(if ($found) { $found.Line } else { 'no FOUND line' }) +
    $(if ($verified) { " | $($verified.Line)" } else { '' }))
  Start-Sleep -Seconds ([int]$T.busy_hold_s)
  $hoBusy = @(Lines-Since $mk | Where-Object { $_.Stage -eq 'HANDOVER' })
  Feed-Release $ToVersion 'none' 'serve'          # once it has installed, nothing newer: no loop
  Clear-AppBusy -M $M
  $mk2 = Get-LogLineCount $ulog
  $hoIdle = Wait-ForLogLine $ulog $mk { param($x) $x.Stage -eq 'HANDOVER' -and $x.Version -eq $NextVersion } ([int]$T.idle_retry_s)
  $back = Wait-ForLogLine -Path $ulog -AfterLine $mk2 -TimeoutSec ([int]$T.update_s) `
    -Match { param($x) $x.Kind -eq 'STARTED' } `
    -GiveUp { param($x) $x.Kind -eq 'UPDATE' -and $x.Stage -eq 'FAILED' } `
    -Progress { param($s) Write-DrillLog "  waiting for the app to come back after its own handover: $s s" }
  Restore-AfterBusy -M $M
  # ...and it must come BACK from that handover: one that never ends is not a pass (R6)
  $extra['waits_while_busy'] = New-Check $(if ($verified -and $hoBusy.Count -eq 0 -and $hoIdle -and $back) { 'pass' } else { 'fail' }) (
    "busy ($($M.busy_description)) for $($T.busy_hold_s) s after VERIFIED: HANDOVER lines $($hoBusy.Count); once idle: " +
    $(if ($hoIdle) { $hoIdle.Line } else { 'no HANDOVER' }) +
    $(if ($back) { " | $($back.Line)" } elseif ($hoIdle) { ' | never came back after that handover' } else { '' }))
  Write-DrillLog ("CHECK waits_while_busy {0} :: {1}" -f $extra['waits_while_busy'].result.ToUpper(), $extra['waits_while_busy'].evidence)
} catch {
  Write-DrillLog "DRILL STOPPED: $($_.Exception.Message)"
  $extra['stopped'] = $_.Exception.Message
} finally {
  try { Stop-AppProcesses $exeName } catch {}
  if ($feedProc) { Stop-FakeFeed $feedProc $feedState }
  Exit-DrillLock $lock
  try { Copy-Item -LiteralPath $ulog -Destination (Join-Path $OutDir "logs\$ToVersion.update.log") -Force } catch {}
  # the FROM's own diagnostics, before -Reset deletes them: the developer's account cannot read
  # the drill profile, so this copy is the only way to see why a FROM step failed (R7)
  foreach ($f in $diagFiles) {
    try {
      if (Test-Path -LiteralPath $f) {
        Copy-Item -LiteralPath $f -Destination (Join-Path $OutDir ("logs\{0}.from-{1}" -f $ToVersion, (Split-Path -Leaf $f))) -Force
      }
    } catch {}
  }
}

foreach ($id in @('start_from_released_build', 'real_update_path', 'new_version_running', 'one_process', 'one_install',
                  'tree_matches_fresh_install', 'shortcuts_open_new', 'relaunched_itself', 'user_data_intact',
                  'no_update_loop', 'sees_next_release', 'bad_download_refused', 'unknown_is_not_no')) {
  if (-not $checks.Contains($id)) { $checks[$id] = New-Check 'fail' 'not measured: the drill stopped before this check' }
}
if ($embedsKey -and -not $checks.Contains('embedded_key_works')) { $checks['embedded_key_works'] = New-Check 'fail' 'not measured: the drill stopped before this check' }
foreach ($k in $extra.Keys) { if ($k -ne 'stopped') { $checks[$k] = $extra[$k] } }

$receipt = [ordered]@{
  schema = 'update-drill/1'
  profile = [string]$M.profile
  app = [string]$M.app
  from_version = [string]$M.from.version
  from_artifact_sha256 = $fromSha
  to_version = $ToVersion
  assets = @([ordered]@{ name = [string]$M.asset_name; sha256 = $toSha })
  drilled_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  machine = "$env:COMPUTERNAME, Windows user '$env:USERNAME'"
  layout = $layout
  drill_log = "drills/logs/$ToVersion.log"
  bootstrap = $false
  routes = @("v$($M.from.version)'s own updater via $($M.from_route.kind) ($($M.drill_repo))", "loopback feed 127.0.0.1:$port for every check made on v$ToVersion")
  checks = $checks
}
if ($embeddedKey) { $receipt['embedded_key'] = $embeddedKey }   # the fingerprint, never the key (KEY_EMBED 6)
if ($M.PSObject.Properties.Name -contains 'not_covered') { $receipt['not_covered'] = @($M.not_covered | ForEach-Object { [string]$_ }) }
if ($extra.Contains('stopped')) { $receipt['stopped'] = $extra['stopped'] }
Write-Receipt (Join-Path $OutDir "$ToVersion.json") $receipt

$failed = @($checks.Keys | Where-Object { $checks[$_].result -ne 'pass' })
if ($failed.Count) {
  Write-DrillLog "RESULT: FAIL - $($failed -join ', ')"
  exit 1
}
Write-DrillLog "RESULT: PASS - every check passed; receipt $(Join-Path $OutDir "$ToVersion.json")"
exit 0
