<#
.SYNOPSIS
  A loopback fake release feed for update drills (UPDATE_DRILL section 3.1, 5a).

.DESCRIPTION
  Answers like GitHub's `releases/latest` plus its asset download, on
  127.0.0.1 only, so a drill can serve N, a corrupted N and a fake N+1
  without publishing anything.

  Everything it serves is read from -StateFile on EVERY request, so the runner
  switches scenarios by rewriting that file; no restart, no IPC:

    {
      "mode":    "serve" | "500" | "403" | "drop",    // what /latest does
      "release": { ...the JSON body of releases/latest... },
      "assets":  { "<file name>": { "file": "<local path>",
                                    "fault": "none" | "truncate" | "flip" | "500" | "drop" } }
    }

  GET /latest            -> the release JSON (or the mode's fault)
  GET /asset/<file name> -> the file, with Range/206 support (resume), or its fault

  Every request is one JSON line in -AccessLog: the oracle the runner reads
  for "no update loop" (no asset fetched) and "sees N+1" (asset fetched).

  Generic: no app name lives here. PowerShell 5.1, no modules.
#>
param(
  [Parameter(Mandatory = $true)][int]$Port,
  [Parameter(Mandatory = $true)][string]$StateFile,
  [Parameter(Mandatory = $true)][string]$AccessLog,
  [string]$StopFile = ''
)

$ErrorActionPreference = 'Stop'
if (-not $StopFile) { $StopFile = "$StateFile.stop" }

function Write-Access([hashtable]$entry) {
  $entry['t'] = (Get-Date).ToString('o')
  $line = ($entry | ConvertTo-Json -Compress -Depth 4)
  [System.IO.File]::AppendAllText($AccessLog, $line + "`n", (New-Object System.Text.UTF8Encoding($false)))
}

function Read-State {
  try {
    $raw = [System.IO.File]::ReadAllText($StateFile)
    return ($raw | ConvertFrom-Json)
  } catch { return $null }
}

function Send-Bytes($stream, [byte[]]$bytes) {
  if ($bytes.Length -gt 0) { $stream.Write($bytes, 0, $bytes.Length) }
}

function Send-Head($stream, [int]$code, [string]$reason, [hashtable]$headers) {
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.Append("HTTP/1.1 $code $reason`r`n")
  foreach ($k in $headers.Keys) { [void]$sb.Append("${k}: $($headers[$k])`r`n") }
  [void]$sb.Append("Connection: close`r`n`r`n")
  Send-Bytes $stream ([System.Text.Encoding]::ASCII.GetBytes($sb.ToString()))
}

function Send-Text($stream, [int]$code, [string]$reason, [string]$body, [string]$type) {
  $b = [System.Text.Encoding]::UTF8.GetBytes($body)
  Send-Head $stream $code $reason @{ 'Content-Type' = $type; 'Content-Length' = $b.Length }
  Send-Bytes $stream $b
}

function Read-Request($stream) {
  # headers only (GET); up to 16 KB
  $buf = New-Object byte[] 16384
  $n = 0
  $stream.ReadTimeout = 10000
  while ($n -lt $buf.Length) {
    $r = $stream.Read($buf, $n, $buf.Length - $n)
    if ($r -le 0) { break }
    $n += $r
    $text = [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
    if ($text.Contains("`r`n`r`n")) { break }
  }
  $text = [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
  $lines = $text -split "`r`n"
  $first = $lines[0] -split ' '
  $h = @{}
  foreach ($l in $lines[1..($lines.Length - 1)]) {
    $i = $l.IndexOf(':')
    if ($i -gt 0) { $h[$l.Substring(0, $i).Trim().ToLower()] = $l.Substring($i + 1).Trim() }
  }
  return @{ method = $first[0]; path = $(if ($first.Length -gt 1) { $first[1] } else { '' }); headers = $h }
}

function Serve-Asset($stream, $req, $spec, [hashtable]$log) {
  $fault = 'none'
  if ($spec.PSObject.Properties.Name -contains 'fault' -and $spec.fault) { $fault = [string]$spec.fault }
  $log['fault'] = $fault
  if ($fault -eq 'drop') { $log['status'] = 'dropped'; return }
  if ($fault -eq '500') { Send-Text $stream 500 'Internal Server Error' 'boom' 'text/plain'; $log['status'] = 500; return }

  $bytes = [System.IO.File]::ReadAllBytes([string]$spec.file)
  if ($fault -eq 'flip') {
    $mid = [int]($bytes.Length / 2)
    $bytes[$mid] = $bytes[$mid] -bxor 0xFF
  }
  $total = $bytes.Length
  $start = 0
  $code = 200; $reason = 'OK'
  $headers = @{ 'Content-Type' = 'application/octet-stream'; 'ETag' = '"drill-' + $total + '"'; 'Accept-Ranges' = 'bytes' }
  $range = $req.headers['range']
  if ($range -and $range -match '^bytes=(\d+)-$') {
    $start = [int]$Matches[1]
    if ($start -ge $total) { $start = 0 } else {
      $code = 206; $reason = 'Partial Content'
      $headers['Content-Range'] = "bytes $start-$($total - 1)/$total"
    }
  }
  $len = [int]($total - $start)
  $headers['Content-Length'] = $len
  Send-Head $stream $code $reason $headers
  $send = $len
  if ($fault -eq 'truncate') { $send = [int]($len / 2) }
  $chunk = 65536
  $off = $start
  $end = $start + $send
  while ($off -lt $end) {
    $c = [int][Math]::Min($chunk, $end - $off)
    $stream.Write($bytes, [int]$off, $c)
    $off += $c
  }
  $log['status'] = $code
  $log['range'] = $range
  $log['bytes'] = $send
}

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
$listener.Start()
Write-Access @{ event = 'listening'; port = $Port }
try {
  while (-not (Test-Path -LiteralPath $StopFile)) {
    if (-not $listener.Pending()) { Start-Sleep -Milliseconds 50; continue }
    $client = $listener.AcceptTcpClient()
    $log = @{}
    try {
      $stream = $client.GetStream()
      $req = Read-Request $stream
      $log['method'] = $req.method; $log['path'] = $req.path
      $state = Read-State
      if ($null -eq $state) {
        Send-Text $stream 503 'Service Unavailable' 'no state' 'text/plain'; $log['status'] = 503
      } elseif ($req.path -eq '/latest') {
        $mode = [string]$state.mode
        $log['mode'] = $mode
        switch ($mode) {
          'drop' { $log['status'] = 'dropped' }
          '500' { Send-Text $stream 500 'Internal Server Error' '{"message":"boom"}' 'application/json'; $log['status'] = 500 }
          '403' { Send-Text $stream 403 'Forbidden' '{"message":"rate limit exceeded"}' 'application/json'; $log['status'] = 403 }
          default {
            $body = ($state.release | ConvertTo-Json -Depth 8)
            Send-Text $stream 200 'OK' $body 'application/json'; $log['status'] = 200
            $log['tag'] = [string]$state.release.tag_name
          }
        }
      } elseif ($req.path -like '/asset/*') {
        $name = [System.Uri]::UnescapeDataString($req.path.Substring(7))
        $log['asset'] = $name
        $spec = $null
        if ($state.assets -and ($state.assets.PSObject.Properties.Name -contains $name)) { $spec = $state.assets.$name }
        if ($null -eq $spec) { Send-Text $stream 404 'Not Found' 'no such asset' 'text/plain'; $log['status'] = 404 }
        else { Serve-Asset $stream $req $spec $log }
      } else {
        Send-Text $stream 404 'Not Found' 'not here' 'text/plain'; $log['status'] = 404
      }
    } catch {
      $log['error'] = $_.Exception.Message
    } finally {
      try { $client.Close() } catch {}
      Write-Access $log
    }
  }
} finally {
  $listener.Stop()
  Write-Access @{ event = 'stopped' }
}
