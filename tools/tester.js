export const meta = {
  name: 'tester',
  description: 'Tester — 3 agent "รีวิวอย่างเดียว" (① ช่องโหว่ฟังก์ชัน · ② ความถูกต้องโค้ด · ③ ภาพรวม perf/UX/โครงสร้าง) ออดิตโปรเจคปัจจุบันแบบขนาน แล้วคืน findings · ❌ agent ไม่แก้/ไม่ spawn ต่อ — Coddy อ่าน findings แล้ววิเคราะห์+แก้เองทั้งหมด',
  phases: [
    { title: 'ออดิต', detail: '3 agent รีวิวอย่างเดียว (lens ละตัว) ขนานกัน → คืน findings P0–P3' },
  ],
}

// ───────────────────────────────────────────────────────────────────────
// เรียกผ่าน: Nick พิมพ์ "Tester" → Coddy ทำตาม command_pattern ข้อ 5:
//   1) เรียก Workflow tool: { scriptPath: "<ไฟล์นี้>", args: { workdir } }
//      workdir = โฟลเดอร์โปรเจคปัจจุบัน (ออดิต in-place แบบ "อ่านอย่างเดียว" — ไม่ต้องทำ worktree เพราะ agent ไม่แก้อะไร)
//   2) ผลกลับมา = findings (P0–P3) จาก 3 lens รวมแล้วเรียงตามความรุนแรง
//   3) Coddy (ตัวหลัก): อ่าน findings → verify กับโค้ดจริง → **แก้เองด้วยมือ 0 agent**
//      → analyze+test → build → อัพ Play internal (mobile) + Drive → อัปเดต memory → รายงาน findings/fixes/สรุปโทเค้น
//
// ⛔ ทำไมต้องเป็น script (เหตุ 2026-06-13): Tester แบบ freeform เคยให้ agent 3 ตัวแตกลูกตัวละ ~30 = ~70 agent.
//    script นี้บังคับด้วยโครงสร้าง: เรียก agent() แค่ "3 ครั้ง" ครั้งเดียว (parallel) ไม่มี loop fan-out ตาม finding,
//    และทุก agent ถูกสั่งเด็ดขาดว่า "รีวิวอย่างเดียว · ห้ามเรียก Agent/Task tool · ห้ามแก้ไฟล์".
//
// 🔎 เรื่อง agentType — พิจารณาแล้ว "ตั้งใจไม่ใส่" (audit ตัวเอง 2026-08-27) ไม่ใช่ลืม:
//    `agentType:'Explore'/'Plan'` จะเป็น hard-lock จริง (ทั้งคู่ไม่มี Agent tool + ไม่มี Edit/Write) แต่มัน
//    เปลี่ยน "บุคลิก" ของ agent ไปด้วย — Explore ถูกออกแบบให้ "อ่านบางส่วนเพื่อหาไฟล์ ไม่ใช่ตรวจงาน"
//    (คำอธิบายของมันเขียนไว้เองว่า "it locates code; it doesn't review or audit it") และ Plan คือสถาปนิก
//    ทั้งสองตัวจะทำให้การรีวิวตื้นลง ซึ่งคือสิ่งเดียวที่สคริปต์นี้มีค่า
//    หลักฐานฝั่งความเสี่ยง: prompt-lock ใช้มาตั้งแต่ 2026-06-13 ยังไม่เคยมีเคส agent แตกลูกอีกเลย และ
//    การกันเชิงโครงสร้างที่ "สำคัญจริง" มีอยู่แล้ว = สคริปต์เรียก parallel() ครั้งเดียว ไม่มีลูปตาม finding
//    → ถ้าวันใดเห็นเกิน 3 จริง ค่อยใส่ (แลกความลึกกับความแน่นอน) — อย่าใส่ไว้ล่วงหน้าโดยไม่มีเหตุ
// ───────────────────────────────────────────────────────────────────────

// ⚠️ args มาถึงสคริปต์เป็น JSON "string" ในฮาร์เนสนี้ (พิสูจน์ 2026-06-13) → ต้อง parse + กัน throw · ❌ ห้ามลบ guard
let _A = args
if (typeof _A === 'string') { try { _A = JSON.parse(_A) } catch { _A = {} } }
_A = _A || {}
const workdir = _A.workdir
if (!workdir)
  return { error:'tester: ไม่มี workdir ใน args — ส่ง args เป็น object {workdir} (Workflow แปลงเป็น string สคริปต์ parse เอง)', findings:[], lenses:[] }

// `notCovered` เป็น required โดยตั้งใจ (audit ตัวเอง 2026-08-27): โปรเจคใหญ่ agent 3 ตัวยังไงก็ต้องตัดขอบเขต
// ถ้าไม่มีช่องให้บอก รายงานที่ตัดไป 80% จะ "อ่านเหมือนตรวจครบ" แล้วสายนี้ไปจบที่ build+อัพ Play เอง
// (รูบริค #26 เรียกการตัดขอบเขตแบบไม่ประกาศว่า "ข้อบกพร่องของตัวรีวิวเอง" — reviver มีช่องนี้อยู่แล้ว ตัวอื่นไม่มี)
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

const LENSES = [
  { key:'functional-gaps',
    title:'① ช่องโหว่ฟังก์ชัน (functional gaps)',
    brief:'ฟีเจอร์ที่ขาด/ทำครึ่งๆ · flow ที่ตัน · ปุ่ม/หน้าที่ไม่ได้ wire · error/empty/edge state ที่ไม่จัดการ · โค้ดที่มีแต่ไม่มี UI (orphaned) · onboarding/permission ที่ทำแอป soft-brick ได้' },
  { key:'code-correctness',
    title:'② ความถูกต้องของโค้ด (code correctness)',
    brief:'บั๊ก logic · race condition · null/empty/ค่าใหญ่/ลำดับ · ทางที่ทำข้อมูลหาย · regression ตรงรอยต่อของการแก้ล่าสุด · serialization ไม่ตรง · การ drop เงียบๆ' },
  { key:'holistic',
    title:'③ ภาพรวม — perf / UX / โครงสร้าง (holistic)',
    brief:'งานที่เปลืองโดยไม่จำเป็น · ผิดโครงสร้าง (dependency ทางเดียว, แยก UI/logic) · pattern ไม่สม่ำเสมอ · security/privacy · perf บน path หลัก · UX สะดุด' },
]

const reviewPrompt = (lens) => [
  `คุณคือ 1 ใน "ทีม Tester" ของ Nick — มี **เป๊ะ 3 ตัว** ทำขนานกัน · คุณรับผิดชอบ lens: **${lens.title}**`,
  lens.brief,
  ``,
  `ออดิตโปรเจคปัจจุบันที่: ${workdir}`,
  `ใช้ **Read / Grep / Glob + Bash แบบอ่านอย่างเดียว** (\`git diff/log/show/grep\`, \`ls\`, \`md5sum\`, \`node --check\`) · เดิน code path จริง end-to-end (ไม่ใช่เดาจากชื่อไฟล์) · cite file:line เป็นหลักฐานเสมอ · แยก "claim (โค้ดบอกว่า)" กับ "ตรวจแล้วยืนยัน/ค้าน"`,
  `⛔ **\`import\` โมดูล = รัน top-level ของมัน** (สร้างโฟลเดอร์ เปิดไฟล์ ต่อ DB ยิงเน็ตได้) — \`python -c "from m import f"\` จึง**ไม่ใช่**การอ่านอย่างเดียว`,
  `   อยากดูค่าจริงของฟังก์ชัน → **คัดตัวฟังก์ชันมาวางใน snippet เปล่าแล้วรัน** ไม่แตะโมดูลจริง`,
  `   (reviver #26 รอบ 3 · B+C เจอตรงกัน: คำเตือนนี้เคยไปถึงแค่ reviver.js ตัวเดียว ทั้งที่ 3 ตัวนี้ก็เพิ่งได้ Bash ไปพร้อมกัน)`,
  `❌ ห้ามรันชุดเทสต์เต็ม/เปิดแอป/build/ติดตั้ง/ยิงเน็ต/เขียน-ลบไฟล์ — พวกนั้นเปลี่ยนสถานะ เป็นขั้นของ Coddy ไม่ใช่ของคุณ`,
  `(ก่อน 2026-08-27 สคริปต์นี้เป็นตัวเดียวใน 4 ตัวที่ยังห้าม Bash ทั้งหมด ทั้งที่เป็นตัวที่ผล review จบด้วยการ build + อัพ Play อัตโนมัติ — reviver #26 บริษัท A ชี้ว่ามันควรได้เครื่องมือพิสูจน์อย่างน้อยเท่าตัวอื่น)`,
  ``,
  `⛔ กฎเหล็ก (Nick #16 — กฎที่โดนละเมิดบ่อยสุด · เหตุ 70-agent 2026-06-13):`,
  `  • ❌ ห้ามเรียก Agent/Task tool · ❌ ห้าม spawn subagent ใดๆ — คุณรีวิว "คนเดียว"`,
  `  • ❌ ห้ามแก้/เขียน/build/run อะไรทั้งสิ้น — คุณ "อ่านแล้วรายงาน" อย่างเดียว`,
  `  • ถ้ารู้สึกว่าต้องมีตัวช่วยเพิ่ม → อย่า spawn เด็ดขาด · เขียนเป็น finding ให้ Coddy แทน`,
  ``,
  `คืนผลเป็น findings ทุกจุดที่เจอ "จริง": severity P0–P3 · title สั้น · file (file:line) · problem · suggestedFix · evidence · เรียง blocker → nit · ❌ ห้าม pad nit · ❌ ห้าม rubber-stamp · ไม่แน่ใจ = ใส่ severity ต่ำไว้ก่อน + บอกว่ายังไม่ยืนยัน`,
  ``,
  `⛔ **บังคับ: ช่อง \`notCovered\`** — เขียนตรงๆ ว่า "อะไรที่คุณไม่ได้ตรวจ" ไฟล์/โฟลเดอร์/ระบบย่อยไหนที่ไม่ได้เปิดอ่าน หรืออ่านแบบผ่านๆ พร้อมเหตุผล`,
  `  โปรเจคใหญ่กว่าที่คนเดียวอ่านไหวเป็นเรื่องปกติ — **การตัดขอบเขตไม่ใช่ความผิด แต่การตัดแล้วไม่บอกคือความผิด**`,
  `  ผลของคุณจะถูกเอาไปแก้โค้ดจริงและ build ต่อ ถ้าคุณเงียบเรื่องที่ไม่ได้ตรวจ ความเงียบนั้นจะถูกอ่านว่า "ตรวจแล้วไม่มีปัญหา"`,
  `  ไม่มีอะไรที่ตัดเลยจริงๆ → เขียนว่า "อ่านครบทุกไฟล์ในขอบเขต" · ❌ ห้ามเว้นว่าง`,
  ``,
  `Coddy (ตัวหลัก) จะอ่าน findings ของคุณแล้ว verify + แก้เอง — หน้าที่คุณคือ "รีวิว" เท่านั้น`,
].join('\n')

phase('ออดิต')

// ⛔ เป๊ะ 3 ตัว — parallel ครั้งเดียว ไม่มี fan-out ตาม finding
const raw = await parallel(LENSES.map(lens => () =>
  agent(reviewPrompt(lens), { label:`รีวิว:${lens.key}`, phase:'ออดิต', schema: FINDINGS })
))

// จับคู่ผลกับ lens ด้วย "ลำดับที่สคริปต์รู้อยู่แล้ว" ไม่ใช่ค่า `lens` ที่ agent พิมพ์กลับมา (audit ตัวเอง 2026-08-27):
// parallel รักษาลำดับ → index i คือ LENSES[i] เสมอ · ถ้า agent คืนสตริงเพี้ยน/ซ้ำกัน การจัดกลุ่มจะมั่วและ
// บอกไม่ได้ว่า "ตัวไหนหายไป" · null = ตัวนั้นตาย (harness คืน null เมื่อ agent ตายหลัง retry หรือถูกข้าม)
const slots   = LENSES.map((lens, i) => ({ lens, report: raw[i] || null }))
const reports = slots.filter(s => s.report)
const dead    = slots.filter(s => !s.report).map(s => s.lens.key)

const order = { P0:0, P1:1, P2:2, P3:3 }
const findings = reports
  .flatMap(s => (s.report.findings || []).map(f => ({ ...f, lens: s.lens.key, lensTitle: s.lens.title })))
  .sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9))
const tally = sev => findings.filter(f => f.severity === sev).length

// ⛔ ออดิตไม่ครบ = ต้องหยุด ไม่ใช่เดินต่อ (#16 FAIL=STOP · audit ตัวเอง 2026-08-27)
// เดิม return บอก `agentsUsed: 3` เสมอแม้ agent ตายไป 1-2 ตัว → สาย Tester เดินต่อไป "แก้ → build → อัพ Play"
// บนออดิตที่ได้แค่ 2/3 โดยไม่มีอะไรสะดุด · ตอนนี้คืนจำนวน "จริง" + ธง degraded + next ที่สั่งหยุด
const degraded = reports.length < LENSES.length

log(`Tester ออดิตเสร็จ: ${reports.length}/${LENSES.length} lens${degraded ? ` ⚠️ ตายไป: ${dead.join(', ')}` : ''} · ${findings.length} findings (P0:${tally('P0')} P1:${tally('P1')} P2:${tally('P2')} P3:${tally('P3')})`)

return {
  agentsExpected: LENSES.length,   // ที่ตั้งใจเปิด = 3 เสมอ (script บังคับ ไม่มีทางเกิน)
  agentsUsed: reports.length,      // ที่คืนผลมาจริง — ❌ ห้ามเปลี่ยนกลับไปเป็น LENSES.length
  degraded,
  deadLenses: dead,
  lenses: reports.map(s => ({ lens: s.lens.key, title: s.lens.title, summary: s.report.summary,
                              count: (s.report.findings || []).length, notCovered: s.report.notCovered || '(ไม่ได้ระบุ)' })),
  findings,
  next: degraded
    ? `🛑 STOP (#16): ออดิตได้แค่ ${reports.length}/${LENSES.length} lens — ขาด ${dead.join(', ')}. ` +
      `❌ ห้ามแก้/build/อัพ Play บนออดิตที่ไม่ครบ · รายงาน Nick ว่าขาด lens ไหนแล้วรอให้เขาสั่งอีกครั้ง (1 trigger = 1 launch)`
    : 'Coddy: อ่าน findings → verify กับโค้ดจริง → แก้เอง (0 agent) → analyze+test → build → อัพ Play internal + Drive → อัปเดต memory → รายงาน findings/fixes/สรุปโทเค้น ' +
      '· อ่าน `lenses[].notCovered` ด้วย — ส่วนที่ไม่ได้ตรวจ ไม่เท่ากับส่วนที่ผ่าน',
}
