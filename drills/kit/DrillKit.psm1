# DrillKit.psm1 - generic helpers for update drills (UPDATE_DRILL section 5a).
#
# No app name or path lives here: everything app-specific comes from the
# project's drills/drill.json manifest and its adapter script. PowerShell 5.1,
# no modules, ASCII only (5.1 reads a BOM-less script in the ANSI code page).

Set-StrictMode -Version 2.0

$script:DrillLogPath = $null

# A run-level stop: Invoke-Drill names a STOP file under its stage (world-writable C:\Users\Public), every polling wait
# checks it, and a hung run ends at its next poll with a FAIL receipt — from ANY account, no admin. HPO's run 3
# (2026-10-31) sat in a 1800-s wait for a feed that had died, owned by the drill account, and nobody could stop it.
$script:DrillStopFile = ''
function Set-DrillStopFile([string]$Path) { $script:DrillStopFile = $Path; if ($Path -and (Test-Path -LiteralPath $Path)) { Remove-Item -LiteralPath $Path -Force } }
function Test-DrillStopFile { if ($script:DrillStopFile -and (Test-Path -LiteralPath $script:DrillStopFile)) { throw "stopped on request: $script:DrillStopFile exists" } }
function Start-DrillLog([string]$Path) {
  $script:DrillLogPath = $Path
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  Set-Content -LiteralPath $Path -Value @() -Encoding UTF8
}

function Write-DrillLog([string]$Message) {
  $line = '{0} {1}' -f (Get-Date).ToString('o'), $Message
  Write-Host $line
  if ($script:DrillLogPath) { Add-Content -LiteralPath $script:DrillLogPath -Value $line -Encoding UTF8 }
}

function Expand-DrillPath([string]$Path) {
  # %VAR% from the environment, plus %DESKTOP% = the shell's real Desktop
  # (it can be redirected to OneDrive, and then %USERPROFILE%\Desktop is wrong)
  $desktop = [Environment]::GetFolderPath('Desktop')
  $p = $Path.Replace('%DESKTOP%', $desktop)
  return [Environment]::ExpandEnvironmentVariables($p)
}

function Get-Sha256([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

function Get-TreeHashes([string]$Root) {
  # relative path (forward slashes) -> sha256, for every file under Root
  $out = @{}
  if (-not (Test-Path -LiteralPath $Root)) { return $out }
  $base = (Resolve-Path -LiteralPath $Root).ProviderPath.TrimEnd('\') + '\'
  Get-ChildItem -LiteralPath $Root -Recurse -File -Force | ForEach-Object {
    $rel = $_.FullName.Substring($base.Length).Replace('\', '/')
    $out[$rel] = Get-Sha256 $_.FullName
  }
  return $out
}

function Compare-Trees([hashtable]$Actual, [hashtable]$Expected, [string[]]$Allow) {
  # differences that are not allowlisted; an allowlist entry matches a path
  # exactly or as a prefix ending in '/'
  $diffs = New-Object System.Collections.ArrayList
  $keys = @($Actual.Keys) + @($Expected.Keys) | Sort-Object -Unique
  foreach ($k in $keys) {
    $allowed = $false
    foreach ($a in $Allow) {
      if ($k -eq $a -or ($a.EndsWith('/') -and $k.StartsWith($a))) { $allowed = $true; break }
    }
    if ($allowed) { continue }
    if (-not $Actual.ContainsKey($k)) { [void]$diffs.Add("missing: $k"); continue }
    if (-not $Expected.ContainsKey($k)) { [void]$diffs.Add("extra: $k"); continue }
    if ($Actual[$k] -ne $Expected[$k]) { [void]$diffs.Add("differs: $k") }
  }
  return ,$diffs
}

function Resolve-Shortcut([string]$Path) {
  # the target a .lnk opens, read the way Explorer reads it
  if (-not (Test-Path -LiteralPath $Path)) { return $null }
  if ($Path.ToLower().EndsWith('.lnk')) {
    $sh = New-Object -ComObject WScript.Shell
    return $sh.CreateShortcut($Path).TargetPath
  }
  return $null
}

function New-Shortcut([string]$Path, [string]$Target) {
  $dir = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $sh = New-Object -ComObject WScript.Shell
  $sc = $sh.CreateShortcut($Path)
  $sc.TargetPath = $Target
  $sc.WorkingDirectory = Split-Path -Parent $Target
  $sc.Save()
}

function Get-AppProcesses([string]$ExeName) {
  # every process of this exe name for THIS user, with its path
  $name = [IO.Path]::GetFileNameWithoutExtension($ExeName)
  $me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  $out = @()
  foreach ($p in @(Get-CimInstance Win32_Process -Filter "Name='$ExeName'" -ErrorAction SilentlyContinue)) {
    $owner = $null
    try { $o = Invoke-CimMethod -InputObject $p -MethodName GetOwner; $owner = "$($o.Domain)\$($o.User)" } catch {}
    if ($owner -and $owner -ne $me) { continue }
    $out += [pscustomobject]@{ Id = [int]$p.ProcessId; Path = [string]$p.ExecutablePath; Name = $name }
  }
  return ,$out
}

function Stop-AppProcesses([string]$ExeName) {
  foreach ($p in (Get-AppProcesses $ExeName)) {
    try { Stop-Process -Id $p.Id -Force -ErrorAction Stop } catch {}
  }
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-AppProcesses $ExeName).Count -gt 0 -and (Get-Date) -lt $deadline) { Test-DrillStopFile; Start-Sleep -Milliseconds 250 }
}

function Test-IsAdmin {
  $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Read-SharedLines([string]$Path) {
  # the lines of a file another process may be appending to right now: .NET's
  # File.ReadAll* refuses a file open for writing (sharing violation), this does not
  for ($i = 0; $i -lt 20; $i++) {
    try {
      $fs = New-Object IO.FileStream($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]'ReadWrite, Delete')
      try { $text = (New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8)).ReadToEnd() } finally { $fs.Dispose() }
      $text = $text.TrimEnd([char[]]"`r`n")
      if ($text -eq '') { return ,@() }
      return ,([string[]]($text -split "`r?`n"))
    } catch [IO.IOException] { Start-Sleep -Milliseconds 100 }
  }
  throw "could not read $Path (still locked after 2 s)"
}

# The two log readers stream their entries (no `return ,$x`): a comma-wrapped
# array goes down a pipeline as ONE object, so `Read-X | Where-Object` would
# test the array itself and never match. Callers wrap them in @(...).
function Read-UpdateLog([string]$Path) {
  # UPDATE_DRILL 3.3 lines, parsed:
  #   <ISO> UPDATE <STAGE> <version> <detail>   and   <ISO> STARTED <version> <exe>
  $out = @()
  if (-not (Test-Path -LiteralPath $Path)) { return }
  $i = 0
  foreach ($line in (Read-SharedLines $Path)) {
    $i++
    if ($line -match '^(\S+) UPDATE (\S+) (\S+) ?(.*)$') {
      $out += [pscustomobject]@{ N = $i; Time = $Matches[1]; Kind = 'UPDATE'; Stage = $Matches[2]; Version = $Matches[3]; Detail = $Matches[4]; Line = $line }
    } elseif ($line -match '^(\S+) STARTED (\S+) (.*)$') {
      $out += [pscustomobject]@{ N = $i; Time = $Matches[1]; Kind = 'STARTED'; Stage = 'STARTED'; Version = $Matches[2]; Detail = $Matches[3]; Line = $line }
    }
  }
  return $out
}

function Wait-ForLogLine([string]$Path, [int]$AfterLine, [scriptblock]$Match, [int]$TimeoutSec,
                         [scriptblock]$GiveUp = $null, [int]$GiveUpGraceSec = 120,
                         [scriptblock]$Progress = $null, [int]$ProgressSec = 60) {
  # The first parsed line after line number AfterLine for which Match is true.
  # GiveUp: a line after which Match cannot come any more (an installer's
  # terminal FAILED); the wait then ends GiveUpGraceSec later instead of at
  # TimeoutSec. Run 1 waited 27 minutes after one. Progress: called with the
  # seconds waited, every ProgressSec, so a long wait is never silent.
  $start = Get-Date
  $deadline = $start.AddSeconds($TimeoutSec)
  $nextProgress = $start.AddSeconds($ProgressSec)
  $gaveUp = $false
  while ((Get-Date) -lt $deadline) {
    foreach ($e in (Read-UpdateLog $Path)) {
      if ($e.N -le $AfterLine) { continue }
      if (& $Match $e) { return $e }
      if ($GiveUp -and -not $gaveUp -and (& $GiveUp $e)) {
        $gaveUp = $true
        $g = (Get-Date).AddSeconds($GiveUpGraceSec)
        if ($g -lt $deadline) { $deadline = $g }
      }
    }
    if ($Progress -and (Get-Date) -ge $nextProgress) {
      & $Progress ([int]((Get-Date) - $start).TotalSeconds)
      $nextProgress = (Get-Date).AddSeconds($ProgressSec)
    }
    Test-DrillStopFile
    Start-Sleep -Milliseconds 500
  }
  return $null
}

function Get-LastLine([string]$Path) {
  # the last non-empty line of a file another process may be appending to; '' if none
  # (assigned, never piped: Read-SharedLines returns ,$array - see H1)
  if (-not (Test-Path -LiteralPath $Path)) { return '' }
  try { $all = Read-SharedLines $Path } catch { return '' }
  for ($i = $all.Count - 1; $i -ge 0; $i--) {
    if ([string]$all[$i] -match '\S') { return [string]$all[$i] }
  }
  return ''
}

function Get-LogLineCount([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return 0 }
  return (Read-SharedLines $Path).Count
}

function Read-AccessLog([string]$Path) {
  $out = @()
  if (-not (Test-Path -LiteralPath $Path)) { return }
  foreach ($line in (Read-SharedLines $Path)) {
    if ($line.Trim()) { try { $out += ($line | ConvertFrom-Json) } catch {} }
  }
  return $out
}

function Initialize-DrillWin32 {
  if ('DrillWin32' -as [type]) { return }
  Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class DrillWin32 {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  public static List<IntPtr> Find(string prefix) {
    var found = new List<IntPtr>();
    EnumWindows((h, l) => {
      var sb = new StringBuilder(512);
      GetWindowText(h, sb, 512);
      if (IsWindowVisible(h) && sb.ToString().StartsWith(prefix)) found.Add(h);
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
'@
}

function Close-WindowByTitlePrefix([string]$Prefix) {
  # posts WM_CLOSE to every visible top-level window whose title starts with Prefix
  Initialize-DrillWin32
  $n = 0
  foreach ($h in [DrillWin32]::Find($Prefix)) { [void][DrillWin32]::PostMessage($h, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero); $n++ }
  return $n
}

function Test-WindowOpen([string]$Prefix) {
  Initialize-DrillWin32
  return ([DrillWin32]::Find($Prefix).Count -gt 0)
}

$DrillLockPath = 'C:\Users\Public\drill-busy.txt'

function Enter-DrillLock([string]$App, [int]$WaitSec, [string]$Path = $DrillLockPath) {
  # UPDATE_DRILL 5.2: one drill at a time on this PC, whatever the app.
  # CreateNew is atomic: two drills starting together cannot both get it.
  $me = "$App | pid $PID | $env:USERNAME | started $((Get-Date).ToString('o'))"
  $deadline = (Get-Date).AddSeconds($WaitSec)
  $said = $false
  while ($true) {
    try {
      $fs = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
      try { $b = [Text.Encoding]::UTF8.GetBytes($me); $fs.Write($b, 0, $b.Length) } finally { $fs.Dispose() }
      Write-DrillLog "drill lock taken: $Path ($me)"
      return $me
    } catch [IO.IOException] {
      $who = '?'
      try { $who = Get-Content -LiteralPath $Path -Raw } catch {}
      if ((Get-Date) -gt $deadline) {
        throw "another drill still holds $Path after $WaitSec s ($who). If no drill is running, Nick removes that file."
      }
      if (-not $said) { Write-DrillLog "another drill is running ($who); waiting up to $WaitSec s"; $said = $true }
      Test-DrillStopFile
      Start-Sleep -Seconds 15
    }
  }
}

function Exit-DrillLock([string]$Token, [string]$Path = $DrillLockPath) {
  # only ever removes the lock this run took
  if (-not $Token) { return }
  try {
    if ((Get-Content -LiteralPath $Path -Raw) -eq $Token) { Remove-Item -LiteralPath $Path -Force; Write-DrillLog "drill lock released: $Path" }
  } catch {}
}

function New-Check([string]$Result, [string]$Evidence) {
  return [ordered]@{ result = $Result; evidence = $Evidence }
}

function Start-FakeFeed([string]$KitDir, [int]$Port, [string]$StateFile, [string]$AccessLog) {
  $stop = "$StateFile.stop"
  if (Test-Path -LiteralPath $stop) { Remove-Item -LiteralPath $stop -Force }
  # 5.1 joins -ArgumentList with spaces and no quoting: quote every value
  $q = { param($v) '"' + $v + '"' }
  $argv = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (& $q (Join-Path $KitDir 'FakeFeed.ps1')),
            '-Port', $Port, '-StateFile', (& $q $StateFile), '-AccessLog', (& $q $AccessLog),
            '-StopFile', (& $q $stop))
  $before = @(Read-AccessLog $AccessLog).Count
  $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $argv -WindowStyle Hidden -PassThru
  $deadline = (Get-Date).AddSeconds(15)
  while ((Get-Date) -lt $deadline) {
    $up = @(Read-AccessLog $AccessLog | Select-Object -Skip $before |
            Where-Object { ($_.PSObject.Properties.Name -contains 'event') -and $_.event -eq 'listening' })
    if ($up.Count -gt 0) { return $p }
    if ($p.HasExited) { break }
    Start-Sleep -Milliseconds 200
  }
  # never leave a half-started feed behind, and say why it did not start
  $why = $(if ($p.HasExited) { "it exited with code $($p.ExitCode)" } else { 'it did not report listening in 15 s' })
  if (-not $p.HasExited) { try { $p.Kill() } catch {} }
  $busy = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  if ($busy.Count) { $why += "; port $Port is already in use by pid $($busy[0].OwningProcess)" }
  throw "the fake feed did not start on 127.0.0.1:${Port}: $why"
}

function Stop-FakeFeed($Process, [string]$StateFile) {
  New-Item -ItemType File -Path "$StateFile.stop" -Force | Out-Null
  if ($Process -and -not $Process.HasExited) {
    if (-not $Process.WaitForExit(5000)) { try { $Process.Kill() } catch {} }
  }
}

function Set-FeedState([string]$StateFile, $State) {
  $json = $State | ConvertTo-Json -Depth 10
  $tmp = "$StateFile.tmp"
  [IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $tmp -Destination $StateFile -Force
}

function New-FeedRelease([string]$Tag, [string]$AssetName, [string]$AssetFile, [string]$DigestSha, [int]$Port) {
  # the shape of GitHub's releases/latest, pointing at this feed
  $size = (Get-Item -LiteralPath $AssetFile).Length
  return [ordered]@{
    tag_name = $Tag; name = $Tag; body = 'drill'; draft = $false; prerelease = $false
    html_url = "http://127.0.0.1:$Port/release/$Tag"
    assets = @([ordered]@{
      name = $AssetName; size = $size; state = 'uploaded'
      digest = "sha256:$DigestSha"
      browser_download_url = "http://127.0.0.1:$Port/asset/$AssetName"
    })
  }
}

function Write-Receipt([string]$Path, $Receipt) {
  $json = $Receipt | ConvertTo-Json -Depth 10
  [IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

Export-ModuleMember -Function Set-DrillStopFile, Test-DrillStopFile
Export-ModuleMember -Function *
