export const meta = {
  name: 'supertester',
  description: 'SuperTester — รีวิวเชิงลึก "เป๊ะ 3 รอบ" รอบละ 3 agent (รีวิวอย่างเดียว) ทำทีละรอบ (review→Coddy แก้→review→แก้→review→แก้). สคริปต์นี้ = เครื่องยนต์ "1 รอบ" (3 agent) · auto-scope จากงานล่าสุด + log 20 entry ล่าสุด · ❌ agent ไม่แก้/ไม่ build/ไม่ spawn — Coddy แก้เอง 0 agent คั่นทุกรอบ',
  phases: [
    { title: 'รีวิว', detail: '3 agent รีวิวอย่างเดียว (lens ตามรอบ) ขนานกัน → คืน findings P0–P3' },
  ],
}

// ───────────────────────────────────────────────────────────────────────
// เรียกผ่าน: Nick พิมพ์ "supertester" → Coddy ทำตาม command_pattern ข้อ 23:
//   0) Coddy หาขอบเขตเอง: อ่าน "สิ่งที่เพิ่งทำล่าสุด" + log\ 20 entry ล่าสุด → สรุปเป็น scope
//   1) วน "เป๊ะ 3 รอบ" — แต่ละรอบ:
//        a) เรียก Workflow: { scriptPath:"<ไฟล์นี้>", args:{ workdir, round, scope } }  → 3 agent รีวิว → findings
//        b) Coddy (ตัวหลัก): verify + **แก้เองด้วยมือ 0 agent**
//      รอบ1 broad → รอบ2 verify+ลึก → รอบ3 final/release-ready  (review→fix ×3)
//   2) จบ 3 รอบ → analyze+test → build → อัพ Play internal (mobile · ❌ ไม่ต้องอัพ Drive) → อัปเดต memory + bug/ + SHARED_LESSONS → รายงาน findings/fixes/สรุปโทเค้น
//
// ⛔ AGENT CAP (Nick #16): 3 ตัว/รอบ · ทำ "ทีละรอบ" (Coddy เรียกสคริปต์นี้ทีละครั้ง) → ไม่เกิน 3 ตัวพร้อมกันเลย
//    รวมทั้งรัน = 9 ตัว แต่ sequential. ❌ ห้ามเรียกสคริปต์นี้ 3 ครั้งพร้อมกัน · ❌ agent ห้ามแตกลูก (review-only)
//    (เหตุที่ต้องเป็นสคริปต์ = บังคับ 3/รอบ เหมือน tester.js กัน fan-out 70-agent 2026-06-13)
// ───────────────────────────────────────────────────────────────────────

// ⚠ args มาถึงสคริปต์เป็น JSON "string" ในฮาร์เนสนี้ (พิสูจน์ 2026-06-13) → ต้อง parse + กัน throw · ❌ ห้ามลบ guard
let _A = args
if (typeof _A === 'string') { try { _A = JSON.parse(_A) } catch { _A = {} } }
_A = _A || {}
const workdir = _A.workdir
if (!workdir)
  return { error:'supertester: ไม่มี workdir ใน args — ส่ง args เป็น object {workdir, round, scope}', findings:[], lenses:[] }
// ⚠ ❌ ห้ามเขียน `Number(x) || 1` (reviver #26 บริษัท A · 2026-08-27): มันกลืน 0, '', NaN และทุกค่าที่ไม่ใช่
// ตัวเลข ให้กลายเป็น "รอบ 1" เงียบๆ — คือบั๊กเดียวกับ `ROUNDS[round] || ROUNDS[1]` ที่เพิ่งลบทิ้งข้างล่าง
// แค่ซ่อนอยู่บรรทัดบนแทน · ไม่ส่ง round มาเลย = ตั้งใจให้เป็นรอบ 1 (ถูกต้อง) · ส่งค่าเพี้ยนมา = ต้องหยุด ไม่ใช่เดา
const _rawRound = _A.round
const round = (_rawRound === undefined || _rawRound === null || _rawRound === '') ? 1 : Number(_rawRound)
const scope = (_A.scope || '').toString().trim()  // สรุป "งานล่าสุด" ที่ Coddy ส่งมา (ว่างได้ — agent อ่าน log เอง)

// `notCovered` required โดยตั้งใจ (audit ตัวเอง 2026-08-27) — ดูเหตุผลเต็มใน tester.js
const FINDINGS = { type:'object', required:['lens','summary','findings','notCovered'], properties:{
  lens:    { type:'string' },
  summary: { type:'string' },
  notCovered: { type:'string' },
  findings:{ type:'array', items:{ type:'object',
    required:['severity','title','file','problem','suggestedFix'], properties:{
      severity:    { type:'string', enum:['P0','P1','P2','P3'] },
      title:       { type:'string' },
      file:        { type:'string' },   // file:line เป็นหลักฐาน
      problem:     { type:'string' },
      suggestedFix:{ type:'string' },
      evidence:    { type:'string' },   // code path / บรรทัดที่ตรวจแล้วยืนยัน
    } } } } }

// lens ลึกขึ้นต่อรอบ — รอบหลังต่อยอดจากของที่เพิ่งแก้
const ROUNDS = {
  1: { name:'broad scan (สแกนกว้างจากงานล่าสุด)', lenses:[
    { key:'functional-gaps', title:'① ช่องโหว่ฟังก์ชัน', brief:'ฟีเจอร์ขาด/ทำครึ่ง · flow ตัน · ปุ่ม/หน้าไม่ wire · error/empty/edge state ไม่จัดการ · โค้ดมีแต่ไม่มี UI · onboarding/permission ที่ทำแอป soft-brick' },
    { key:'code-correctness', title:'② ความถูกต้องโค้ด', brief:'บั๊ก logic · race · null/empty/ค่าใหญ่/ลำดับ · ทางทำข้อมูลหาย · regression ตรงรอยต่อการแก้ล่าสุด · serialization ไม่ตรง · drop เงียบๆ' },
    { key:'holistic', title:'③ ภาพรวม perf/UX/โครงสร้าง', brief:'งานเปลืองเกินจำเป็น · ผิดโครงสร้าง · pattern ไม่สม่ำเสมอ · security/privacy · perf บน path หลัก · UX สะดุด' },
  ]},
  2: { name:'verify + deeper (ตรวจของที่แก้ + ขุดลึก)', lenses:[
    { key:'fix-verify-regression', title:'① ตรวจฟิกซ์รอบก่อน + regression', brief:'ของที่เพิ่งแก้รอบที่แล้ว แก้จริง/ครบทุกจุดไหม (grep หา occurrence ที่ตกหล่น) · การแก้สร้างบั๊กใหม่ตรงรอยต่อไหม · อ่าน log/bug ล่าสุดเทียบกับโค้ดจริง' },
    { key:'deep-correctness-data', title:'② correctness ลึก + ความปลอดภัยข้อมูล', brief:'edge/null/concurrency/ลำดับ · atomic write / clear-then-parse / WAL / serialization ฟิลด์ใหม่ · ทางที่ข้อมูลหายตอน crash/ไฟดับ · silent drop · ดูเทียบ SHARED_LESSONS' },
    { key:'security-privacy', title:'③ security / privacy', brief:'secret ใน tracked file · key/permission/allowBackup · auth บน endpoint · path traversal/zip-slip · ข้อมูลลับใน backup/log' },
  ]},
  3: { name:'final / release-ready (ปิดจ็อบ)', lenses:[
    { key:'acceptance-vs-intent', title:'① ทำได้ตรงเจตนาจริงไหม (end-to-end)', brief:'เดิน flow จริงทั้งเส้นเทียบกับ "สิ่งที่ Nick สั่งล่าสุด" (จาก log/scope) · ผลลัพธ์ตรงเจตนาไหม · acceptance จริง ไม่ใช่แค่ unit test เขียว' },
    { key:'cross-file-consistency', title:'② regression sweep + ความสม่ำเสมอข้ามไฟล์', brief:'กวาดทั้งบริเวณที่แตะ · version/const หลายที่ตรงกันไหม · สำเนา logic ที่ลืมอัพเดท · dead code/TODO ที่ค้าง' },
    { key:'release-readiness', title:'③ พร้อมปล่อย', brief:'กับดัก build/release (versionCode, R8, manifest, obfuscate) · UX polish รอบสุดท้าย · copy/marketing ตรงความจริง · ของที่ต้องทำก่อนปล่อยจริง' },
  ]},
}
// ⛔ ไม่ตกกลับไปรอบ 1 เงียบๆ (audit ตัวเอง 2026-08-27): เดิมเขียน `ROUNDS[round] || ROUNDS[1]` → ส่ง round:4 มา
// (พิมพ์ผิด / off-by-one ในลูป 3 รอบ) แล้ว prompt จะบอก agent ว่า **"รอบที่ 4/3 (broad scan)"** คือขัดกันเอง:
// สั่งว่าเป็นรอบปิดจ็อบ แต่ยัดเลนส์สแกนกว้างของรอบ 1 ให้ · fail fast ด้วย 0 agent ดีกว่า (#16 diagnose-0-agent-first)
const R = ROUNDS[round]
if (!R)
  return { error:`supertester: round ต้องเป็น 1, 2 หรือ 3 เท่านั้น — ได้มา ${JSON.stringify(_A.round)} · ไม่เปิด agent ใดๆ`,
           findings:[], lenses:[] }

// ⛔ รอบ 2-3 ต้องมี scope (audit ตัวเอง 2026-08-27): สคริปต์นี้ "ไม่เก็บ state ข้ามรอบ" — แต่ละรอบคือการเรียกคนละครั้ง
// เลนส์ของรอบ 2 คือ "① ตรวจฟิกซ์รอบก่อน + regression" ซึ่งต้องมี "รายการของที่แก้ไปรอบก่อน" ถึงจะตรวจได้
// เดิม scope เป็น optional และ prompt เขียนว่า "**สมมติ**รอบก่อนแก้ไปบางส่วนแล้ว" → เรียกรอบ 2 โดยไม่ใส่ scope
// = agent เดาเอาเองว่ารอบก่อนแก้อะไร → คุณค่าทั้งหมดของดีไซน์ 3 รอบ (verify → ขุดลึก) หายเงียบๆ
// กลายเป็นสแกนกว้าง 3 ครั้ง · ตอนนี้บังคับให้ Coddy ส่งมา ไม่งั้นหยุดตั้งแต่ 0 agent
if (round >= 2 && !scope)
  return { error:`supertester รอบ ${round}: ต้องส่ง \`scope\` มาด้วย = สรุปว่ารอบก่อนแก้อะไรไปบ้าง (ไฟล์+สิ่งที่แก้) ` +
                 `เพราะเลนส์ "${R.lenses[0].title}" ตรวจของที่เพิ่งแก้ ถ้าไม่มีรายการ agent จะเดา · ไม่เปิด agent ใดๆ`,
           findings:[], lenses:[] }

const reviewPrompt = (lens) => [
  `คุณคือ 1 ใน "ทีม SuperTester" ของ Nick — **เป๊ะ 3 ตัว** ทำขนานกัน · นี่คือ **รอบที่ ${round}/3 (${R.name})** · คุณรับผิดชอบ lens: **${lens.title}**`,
  lens.brief,
  ``,
  `ออดิตโปรเจคปัจจุบันที่: ${workdir}`,
  scope ? `ขอบเขตที่ Coddy สรุปจากงานล่าสุด: ${scope}` : ``,
  `**ก่อนรีวิว**: อ่าน \`log/\` ไฟล์ล่าสุด (20 entry ล่าสุด) + \`bug/\` ล่าสุด + ดูการเปลี่ยนแปลงล่าสุด (git ถ้ามี) เพื่อเข้าใจ "สิ่งที่เพิ่งทำ" แล้วโฟกัสรีวิวบริเวณนั้นเป็นหลัก (แต่จับบั๊กร้ายแรงนอกบริเวณได้ด้วย)`,
  round >= 2 ? `รอบนี้ต่อยอด: **ของที่รอบก่อนแก้ไปแล้วอยู่ในบรรทัด "ขอบเขต" ข้างบน** (สคริปต์บังคับให้ Coddy ส่งมา) — ตรวจว่าแก้ครบทุกจุดจริงไหม (grep หา occurrence ที่ตกหล่น) · การแก้สร้างบั๊กใหม่ตรงรอยต่อไหม · แล้วขุดลึกกว่ารอบก่อน · ❌ อย่าเดาเอาเองว่ารอบก่อนแก้อะไร` : ``,
  `ใช้ **Read / Grep / Glob (+ Bash อ่านอย่างเดียว เช่น git diff/log) เท่านั้น** · เดิน code path จริง end-to-end (ไม่เดาจากชื่อไฟล์) · cite file:line เสมอ · แยก "claim" กับ "ยืนยัน/ค้านแล้ว"`,
  `⛔ **\`import\` โมดูล = รัน top-level ของมัน** (สร้างโฟลเดอร์ เปิดไฟล์ ต่อ DB ยิงเน็ตได้) — \`python -c "from m import f"\` จึง**ไม่ใช่**การอ่านอย่างเดียว`,
  `   อยากดูค่าจริงของฟังก์ชัน → **คัดตัวฟังก์ชันมาวางใน snippet เปล่าแล้วรัน** ไม่แตะโมดูลจริง`,
  `   (reviver #26 รอบ 3 · B+C เจอตรงกัน: คำเตือนนี้เคยไปถึงแค่ reviver.js ตัวเดียว ทั้งที่ 3 ตัวนี้ก็เพิ่งได้ Bash ไปพร้อมกัน)`,
  ``,
  `⛔ กฎเหล็ก (Nick #16 — เหตุ 70-agent 2026-06-13):`,
  `  • ❌ ห้ามเรียก Agent/Task tool · ❌ ห้าม spawn subagent — คุณรีวิว "คนเดียว"`,
  `  • ❌ ห้ามแก้/เขียน/build/run อะไรที่เปลี่ยนสถานะ — "อ่านแล้วรายงาน" อย่างเดียว`,
  `  • ต้องการตัวช่วย → เขียนเป็น finding ให้ Coddy แทน · ❌ ห้าม spawn`,
  ``,
  `คืน findings ทุกจุดที่เจอ "จริง": severity P0–P3 · title สั้น · file (file:line) · problem · suggestedFix · evidence · เรียง blocker→nit · ❌ ห้าม pad nit · ❌ ห้าม rubber-stamp · ไม่แน่ใจ = severity ต่ำ + บอกว่ายังไม่ยืนยัน`,
  ``,
  `⛔ **บังคับ: ช่อง \`notCovered\`** — เขียนตรงๆ ว่าอะไรที่คุณ "ไม่ได้ตรวจ" (ไฟล์/โฟลเดอร์/ระบบย่อยที่ไม่ได้เปิด หรืออ่านผ่านๆ) พร้อมเหตุผล`,
  `  ตัดขอบเขตไม่ใช่ความผิด — **ตัดแล้วไม่บอกคือความผิด** · ผลของคุณจะถูกเอาไปแก้โค้ดจริงและ build ต่อ ความเงียบจะถูกอ่านว่า "ตรวจแล้วผ่าน"`,
  `  ไม่ได้ตัดอะไรเลย → เขียน "อ่านครบทุกไฟล์ในขอบเขต" · ❌ ห้ามเว้นว่าง`,
].filter(Boolean).join('\n')

phase('รีวิว')

// ⛔ เป๊ะ 3 ตัว — parallel ครั้งเดียว ไม่มี fan-out ตาม finding
const raw = await parallel(R.lenses.map(lens => () =>
  agent(reviewPrompt(lens), { label:`R${round}:${lens.key}`, phase:'รีวิว', schema: FINDINGS })
))

// จับคู่ผลกับ lens ด้วยลำดับที่สคริปต์รู้ ไม่ใช่ค่า `lens` ที่ agent พิมพ์กลับมา (audit ตัวเอง 2026-08-27) — ดู tester.js
const slots   = R.lenses.map((lens, i) => ({ lens, report: raw[i] || null }))
const reports = slots.filter(s => s.report)
const dead    = slots.filter(s => !s.report).map(s => s.lens.key)

const order = { P0:0, P1:1, P2:2, P3:3 }
const findings = reports
  .flatMap(s => (s.report.findings || []).map(f => ({ ...f, lens: s.lens.key, lensTitle: s.lens.title })))
  .sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9))
const tally = sev => findings.filter(f => f.severity === sev).length

// ⛔ รีวิวไม่ครบ = หยุด ไม่ใช่เดินต่อ (#16 FAIL=STOP · audit ตัวเอง 2026-08-27) — เดิมคืน agentsUsed:3 เสมอ
// แม้ตายไป 1-2 ตัว แล้วสายนี้เดินต่อไป "แก้ → รอบถัดไป → build → อัพ Play" บนรีวิวที่ไม่ครบ
const degraded = reports.length < R.lenses.length

log(`SuperTester รอบ ${round}/3 (${R.name}) เสร็จ: ${reports.length}/${R.lenses.length} lens${degraded ? ` ⚠ ตายไป: ${dead.join(', ')}` : ''} · ${findings.length} findings (P0:${tally('P0')} P1:${tally('P1')} P2:${tally('P2')} P3:${tally('P3')})`)

return {
  round,
  roundName: R.name,
  agentsExpected: R.lenses.length,   // ที่ตั้งใจเปิด = 3 เสมอ
  agentsUsed: reports.length,        // ที่คืนผลมาจริง — ❌ ห้ามเปลี่ยนกลับไปเป็น R.lenses.length
  degraded,
  deadLenses: dead,
  lenses: reports.map(s => ({ lens: s.lens.key, title: s.lens.title, summary: s.report.summary,
                              count: (s.report.findings || []).length, notCovered: s.report.notCovered || '(ไม่ได้ระบุ)' })),
  findings,
  next: degraded
    ? `🛑 STOP (#16): รอบ ${round} ได้แค่ ${reports.length}/${R.lenses.length} lens — ขาด ${dead.join(', ')}. ` +
      `❌ ห้ามแก้/ขึ้นรอบถัดไป/build บนรีวิวที่ไม่ครบ · รายงาน Nick แล้วรอให้เขาสั่งอีกครั้ง (1 trigger = 1 launch)`
    : (round < 3
        ? `Coddy: verify + แก้เอง (0 agent) → เรียกสคริปต์นี้ "รอบ ${round + 1}" พร้อมส่ง \`scope\` = สรุปว่ารอบนี้แก้อะไรไปบ้าง (บังคับ)`
        : `Coddy: verify + แก้เอง (0 agent) → จบ 3 รอบ → analyze+test → build → อัพ Play internal (❌ ไม่ต้องอัพ Drive) → อัปเดต memory/bug/SHARED_LESSONS → รายงาน findings/fixes/สรุปโทเค้น`)
    + ' · อ่าน `lenses[].notCovered` ด้วย — ส่วนที่ไม่ได้ตรวจ ไม่เท่ากับส่วนที่ผ่าน',
}
