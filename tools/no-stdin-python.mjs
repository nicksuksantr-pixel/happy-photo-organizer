#!/usr/bin/env node
// PreToolUse guard for Bash / PowerShell: refuse a Python started on STDIN (`python -`, `python -B -`, `py -`).
//
// WHY THIS FILE EXISTS
// Promoted to the house (command_pattern #29, Nick 2026-11-28) from SHIP-MONITORING, where it was written: there it was
// Coddy's single most repeated mistake -- twelve times by 2026-11-28 a command of the shape
//     python -B - < /dev/null 2>/dev/null; echo skip
// was sent -- as a "placeholder", a "guard", a "skip" -- while deciding what to do next. With nothing on stdin
// that Python waits for a script that never comes, and the call hangs for its whole timeout (120 s, then a
// background task to stop). It was written down in memory after the 9th, the 10th, the 11th... and repeated
// forty minutes after the 11th. A note only works if somebody opens it at the right moment; this does not need
// anybody to remember anything (SM memory/REPEAT_MISTAKES.md #1). The Director repeated it the same day, while
// writing #29, in a repo the hook did not yet reach -- which is why it ships to every repo now.
//
// The rule it enforces: a script goes in a FILE (the Write tool) and runs as `python -B path.py < /dev/null`.
// Only the COMMAND position is checked (start of a line or after ; & | ( $( ), so a commit message or a grep
// pattern that merely mentions the words is not refused.
//
// Blocks by writing the reason to stderr and exiting 2. Fails OPEN on anything it cannot parse.

import fs from 'node:fs'

const read = (fd) => { try { return fs.readFileSync(fd, 'utf8') } catch { return '' } }
const allow = () => process.exit(0)

let hook = {}
try { hook = JSON.parse(read(0) || '{}') } catch { allow() }
if (hook.tool_name !== 'Bash' && hook.tool_name !== 'PowerShell') allow()
const cmd = String((hook.tool_input || {}).command || '')

// <command position> [VAR=val ...] [& ] [path/]python[3[.x]][.exe] | py[.exe]  [-X ...]  -   (a lone dash)
const RX = new RegExp(
  String.raw`(?:^|[;&|(\n]|\$\()\s*` +                       // where a command starts
  String.raw`(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*` +             // env assignments
  String.raw`(?:&\s*)?["']?(?:[^\s"';|&]*[\\/])?` +            // PowerShell call operator, a path
  String.raw`(?:python(?:3(?:\.\d+)?)?|py)(?:\.exe)?["']?` +    // the interpreter
  String.raw`(?:\s+-[A-Za-z]+)*` +                             // its switches (-B, -u, -I ...)
  String.raw`\s+-(?=\s|$|[;|&)<>])`,                           // ...and then a lone "-": the script is stdin
  'm')

if (RX.test(cmd)) {
  process.stderr.write(
    'REFUSED (#29, the most repeated slip in the house):this starts Python reading its script from STDIN (`python -`). ' +
    'With nothing piped in it waits for ever -- the 120 s hang that happened twelve times in SM alone. ' +
    'Write the script to a file with the Write tool and run `python -B <file> < /dev/null`. ' +
    'If you only meant to pause or "skip": send no command at all.\n')
  process.exit(2)
}
allow()
