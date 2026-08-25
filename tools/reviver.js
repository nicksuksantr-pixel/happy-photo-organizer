export const meta = {
  name: 'reviver',
  description: 'reviver — 3 agent "รีวิวอย่างเดียว" ขนานกัน เดิน **ครบทั้ง 7 พาทของ CODE_REVIEW_PROCEDURE** (00 ใบรีวิว → 01 ขอบเขต → 02 แผนที่ → 03 อ่าน → 04 กวาดมิติ → 05 พิสูจน์ 5 ด่าน → 06 เขียน+คะแนน → 07 ปิดงาน) · lens ละกลุ่มมิติ (① A,D ตรรกะ+สถานะ · ② B,C ทางที่พัง+ความเชื่อถือ · ③ H,E,F,J,G,I สอดคล้อง+สัญญา+เทสต์+ที่ขาด) · ทุกตัวส่ง "ใบรีวิว" + findings + cleared กลับมา → Coddy ชนผลกันเพื่อ **ตรวจทานกันเอง** → คะแนน = มิติต่ำสุด · ❌ agent ไม่แก้/ไม่ spawn ต่อ · ❌ ไม่ auto-fix',
  phases: [
    { title: 'รีวิว', detail: '3 agent ขนานกัน · แต่ละตัวเดินครบ 7 พาท แล้วส่งใบรีวิว+findings+cleared+คะแนนรายมิติ' },
  ],
}

// ───────────────────────────────────────────────────────────────────────
// เรียกผ่าน: Nick พิมพ์ "reviver" (หรือ "reviewer") → Coddy ทำตาม command_pattern ข้อ 26:
//   1) Workflow tool: { scriptPath:"<ไฟล์นี้>", args:{ workdir, target } }
//      workdir = โฟลเดอร์โปรเจคปัจจุบัน · target = diff/commit/path (ไม่ใส่ = การเปลี่ยนแปลงปัจจุบัน)
//   2) ผลกลับ = ใบรีวิว 3 ใบ + findings + cleared + conflicts + คะแนนรายมิติ
//   3) Coddy (0 agent): ชน conflicts กับโค้ดจริง → verify → รายงาน · ❌ ไม่แก้อัตโนมัติ (reviver = คำสั่งรีวิว)
//
// ⛔ กฎ #16: เรียก agent() แค่ "3 ครั้ง" ครั้งเดียว (parallel) · ไม่มี fan-out ตาม finding ·
//    agent ทุกตัวถูกสั่งเด็ดขาด "รีวิวอย่างเดียว · ห้ามเรียก Agent/Task tool · ห้ามแก้ไฟล์"
// 📐 Nick 2026-08-17: "อย่าไปย่อ ให้ทำงานเต็มแบบที่เราออกแบบกันไว้" → prompt เดินครบ 7 พาท
//    และ schema บังคับให้ส่ง "ใบรีวิว" กลับมาเป็นหลักฐานว่าทำจริง ไม่ใช่ข้ามไปเดา
// ───────────────────────────────────────────────────────────────────────

// ⚠️ args มาถึงสคริปต์เป็น JSON "string" ในฮาร์เนสนี้ (พิสูจน์ 2026-06-13) → ต้อง parse + กัน throw · ❌ ห้ามลบ guard
let _A = args
if (typeof _A === 'string') { try { _A = JSON.parse(_A) } catch { _A = {} } }
_A = _A || {}
const workdir = _A.workdir
const target = (_A.target || '').trim()
if (!workdir)
  return { error:'reviver: ไม่มี workdir ใน args — ส่ง args เป็น object {workdir, target?}', findings:[], cleared:[], lenses:[] }

const REPORT = { type:'object',
  required:['lens','summary','sheet','dimensionScores','findings','cleared','notCovered'],
  properties:{
    lens:    { type:'string' },
    summary: { type:'string', description:'2-4 ประโยค: มุมนี้เห็นอะไร และคุณเลือกรีวิวอะไร' },

    // ── พาท 00 ใบรีวิว — บังคับส่งกลับ เป็นหลักฐานว่าเดินครบพาท 01-03 จริง ──
    sheet: { type:'object', required:['header','map','trace','questions'], properties:{
      header: { type:'object', required:['target','intent','intentTag','inScope','outOfScope','depth','cutReason'], properties:{
        target:     { type:'string', description:'1.1 ref จริงที่รีวิว' },
        intent:     { type:'string', description:'1.2 ประโยคเดียว "หลังแก้แล้ว X ควร Y" ที่พิสูจน์ผิดได้' },
        intentTag:  { type:'string', description:'STATED | INFERRED | ASSUMED (1.2/1.3)' },
        inScope:    { type:'array', items:{ type:'string' }, description:'1.4 ถัง IN' },
        outOfScope: { type:'array', items:{ type:'string' }, description:'1.4 ถัง OUT + เหตุผลคำเดียว' },
        depth:      { type:'string', description:'1.6 skim | standard | deep' },
        cutReason:  { type:'string', description:'1.5 ตัดอะไรทิ้งเพราะกฎไหน · ไม่ได้ตัด = "ไม่ได้ตัด"' },
      } },
      map: { type:'object', required:['entryPoints','callers','siblings','instances'], properties:{
        entryPoints:{ type:'array', items:{ type:'string' }, description:'2.1 file:line → ชื่อ (ไม่เกิน 3)' },
        callers:    { type:'array', items:{ type:'string' }, description:'2.3 symbol: file:line,... (N) · N=0 ต้องระบุว่าโค้ดตายหรือคนนอกใช้' },
        siblings:   { type:'array', items:{ type:'string' }, description:'2.4 path:line — เป็นคู่ของอะไร · ไม่มีให้ใส่ "none — ตัวแรกของชนิดนี้"' },
        instances:  { type:'string', description:'2.5 dev=<path> · installed/build=<path> · เหมือนหรือต่าง' },
      } },
      trace:     { type:'array', items:{ type:'string' }, description:'3.2 file:line → file:line — ส่งอะไรต่อ · จากจุดเข้าถึงจุดที่มีผลจริง ห้ามขาดตอน' },
      questions: { type:'array', items:{ type:'string' }, description:'[Q] คำถามค้าง Qn: ข้ออ้าง + สถานะ' },
    } },

    // ── พาท 04 + 06.2 ──
    dimensionScores:{ type:'array', description:'คะแนน 1-5 เฉพาะมิติที่ lens นี้รับผิดชอบ (0 = N/A ต้องมีเหตุผล) — ห้ามเว้นมิติไว้เฉยๆ', items:{ type:'object',
      required:['dimension','score','why'], properties:{
        dimension:{ type:'string', description:'ตัวอักษร A-J + ชื่อมิติ' },
        score:    { type:'number', description:'1-5 · 0 = N/A' },
        why:      { type:'string', description:'อะไรกดคะแนน หรือทำไม N/A' },
      } } },

    // ── พาท 06.1 ──
    findings:{ type:'array', items:{ type:'object',
      required:['severity','title','file','problem','failureScenario','evidence','gatesPassed','suggestedFix','blastRadius'], properties:{
        severity:       { type:'string', enum:['P0','P1','P2','P3'] },
        title:          { type:'string' },
        file:           { type:'string', description:'file:line — บังคับ' },
        dimension:      { type:'string', description:'มิติ A-J ที่เข้าข่าย' },
        problem:        { type:'string', description:'ผิดตรงไหน 1 ประโยค' },
        failureScenario:{ type:'string', description:'input จริง → ผลผิดจริง · ⛔ เขียนไม่ได้ = ห้ามยื่น' },
        evidence:       { type:'string', description:'อ่านบรรทัดไหน / เดิน path ไหน แล้วยืนยัน' },
        gatesPassed:    { type:'string', description:'พาท 05 — ผ่านด่านไหนบ้างจาก 5 ด่าน (ระบุทีละด่าน)' },
        suggestedFix:   { type:'string' },
        blastRadius:    { type:'string', description:'แก้แล้วกระทบอะไร' },
      } } },

    // ── พาท 06.3 = [DROP] · เป็นกลไกตรวจทานกันเองระหว่าง lens ──
    cleared:{ type:'array', description:'[DROP] สิ่งที่ดูน่าสงสัยแต่ตรวจแล้วไม่ใช่ปัญหา (รวมของที่ตกด่านในพาท 05)', items:{ type:'object',
      required:['what','file','whyNotAProblem'], properties:{
        what:          { type:'string' },
        file:          { type:'string' },
        whyNotAProblem:{ type:'string', description:'หลักฐานที่ทำให้ตกไป' },
      } } },

    // ── พาท 06.4 ──
    notCovered:{ type:'string', description:'สิ่งที่ lens นี้ไม่ได้ตรวจ + เพราะอะไร · ⛔ ห้ามเว้นว่าง ช่องว่างอ่านเหมือน "ตรวจแล้วผ่าน"' },

    // ── พาท 07.2 ──
    crossProjectLesson:{ type:'string', description:'ถ้าบั๊กชนิดนี้กัดโปรเจคอื่นได้: อาการ → สาเหตุ → วิธีกัน (1 บรรทัด) · ไม่มีให้ใส่ "-"' },
  } }

const LENSES = [
  { key:'logic-state',
    title:'① ตรรกะ + สถานะ (มิติ A ความถูกต้อง, D สถานะและข้อมูล)',
    pass:'พาท 04 รอบ 1 "ตรรกะ" — อ่านช้าทีละบรรทัดบนเส้นทางใน [TRACE] ที่คุณเพิ่งเดินมา',
    brief:[
      'A: ชื่อ/docstring ตรงพฤติกรรมจริงไหม (ชื่อที่โกหก = บั๊กในตัวมันเอง) · ค่าขอบ 0/1/ว่าง/null/ติดลบ/ค่าสูงสุด/ค่าซ้ำ · off-by-one ใน loop และ slice · ตัวเลข: ปัดเศษ, float กับเงิน, หารศูนย์ · เวลา: timezone, DST, **นาฬิกาเดินถอยหลัง**, wall clock vs monotonic · encoding: UTF-8/BOM/cp1252 · **รันซ้ำได้ไหม (idempotent)** — กดสองครั้ง/retry/ข้อความมาซ้ำ',
      'D: ใครเป็นเจ้าของ state นี้ — แหล่งเดียวหรือซ้ำหลายที่ (**grep ทุกจุดที่เขียนค่ามัน** อย่าเชื่อคอมเมนต์ที่บอกว่าใครเป็นเจ้าของ) · รอดรีสตาร์ทไหม / ไฟดับกลางคันแล้วพังไหม · ข้อมูลเก่า/เวอร์ชันเก่าเกิดอะไรขึ้น (migration) · cache key ผูกกับอะไร',
    ].join('\n  ') },
  { key:'failure-trust',
    title:'② ทางที่พัง + ความเชื่อถือ (มิติ B พฤติกรรมตอนพัง, C เส้นแบ่งความเชื่อถือ)',
    pass:'พาท 04 รอบ 2 "ทางที่พัง" — อ่าน **เฉพาะ** `if` / `try` / `return` ก่อนกำหนด · ข้ามทางปกติทั้งหมด',
    brief:[
      'B: **fail-open หรือ fail-closed** — เมื่อการตรวจสอบทำงานไม่ได้ มันปล่อยผ่านหรือปฏิเสธ (ช่องที่พบบ่อยที่สุด) · error ถูกกลืนเงียบไหม (`except: pass`) · **ผู้ใช้เห็นความล้มเหลวไหม — log อย่างเดียวไม่นับ** · พังกลางทาง: state ค้างครึ่ง ไม่มี rollback · retry วนไม่รู้จบ / retry สิ่งที่ retry ไม่ได้ · cleanup บนทาง error (ไฟล์ ล็อก ซ็อกเก็ต เธรด)',
      'C: ข้อมูลข้ามจาก "ไม่เชื่อถือ" มา "เชื่อถือ" ตรงไหน · **ตัวตนอ่านจากช่องทางที่ตรวจแล้ว หรือจาก payload** · จุดฉีด: SQL, shell string, innerHTML, path traversal · สิทธิ์เช็คถูกชั้นไหม มีทางเข้าอื่นที่เลี่ยงได้ไหม · **มีอะไร self-elevate สิทธิ์ตัวเองไหม**',
    ].join('\n  ') },
  { key:'consistency-gaps',
    title:'③ สอดคล้อง + สัญญา + เทสต์ + สิ่งที่ขาด (มิติ H, E, F, J · กวาด G, I)',
    pass:'พาท 04 รอบ 3 "เทียบ" (เปิดไฟล์พี่น้องจาก 2.4 ไว้ **ข้างกัน** แล้วไล่ต่างทีละจุด) + รอบ 4 "รอบนอก" (กวาดเร็ว ใช้ grep/linter มากกว่าสายตา)',
    brief:[
      'H ⭐ **เทียบฟังก์ชันพี่น้องก่อนเป็นอันดับแรก** — สองตัวทำงานชนิดเดียวกัน ตัวหนึ่งมียามอีกตัวไม่มี = ตัวใดตัวหนึ่งผิดเสมอ (วิธีหาบั๊กที่เร็วที่สุดโดยไม่ต้องเข้าใจทั้งระบบ) · ตรรกะที่เคยซ้ำกันแล้วแยกทาง ตัวหนึ่งได้รับการแก้ อีกตัวไม่ได้',
      'E: backward compat (client เก่า ไฟล์เก่า firmware เก่า) · **ค่า default เป็นตัวเลือกที่ปลอดภัยไหม** · API ใช้ผิดง่ายไหม (bool ลอยๆ, ลำดับ arg ที่สลับได้)',
      'F: เทสพฤติกรรมหรือเทสวิธีเขียน · **ถ้าย้อนโค้ดที่แก้ออก เทสต์ต้องแดง — ถ้ายังเขียว เทสต์นั้นไร้ค่า** · ทางที่ผิดพลาดถูกเทสไหม · เทสต์ assert "ข้อความในไฟล์" แทนพฤติกรรมไหม · เทสต์แตะสโตร์จริง/ยิง API จริง/สร้างเธรดค้างไหม',
      'J: เทสต์สำหรับบั๊กที่เพิ่งแก้ · เอกสาร/CODEMAP/V-Log ที่ควรอัพเดท · ทางถอย/migration · **ที่อื่นที่ต้องแก้แบบเดียวกัน (grep pattern เดิม) — ตอบด้วยผลค้นหาจริง ไม่ใช่ความรู้สึก**',
      'G/I (กวาดเร็ว): คอมเมนต์อธิบาย "ทำไม" ไม่ใช่ "อะไร" · เข้าสำนวนโค้ดรอบข้าง · โค้ดตาย/TODO ค้าง/debug print · ของที่ **ไม่มีขอบเขต** · query ใน loop · งานหนักใต้ล็อก · เรียก API ช้าบนเธรด UI',
    ].join('\n  ') },
]

const scopeLine = target
  ? `**${target}**`
  : `**การเปลี่ยนแปลงปัจจุบันของโปรเจค** — หาเองจาก git (uncommitted diff ก่อน · tree สะอาด → commit ล่าสุด) แล้วเขียนไว้ใน sheet.header.target ว่าคุณเลือกอะไร`

const reviewPrompt = (lens) => [
  `คุณคือ 1 ใน "ทีม reviver" ของ Nick — **เป๊ะ 3 ตัว** ทำขนานกัน คนละกลุ่มมิติ`,
  `คุณรับผิดชอบ lens: **${lens.title}**`,
  `  ${lens.brief}`,
  ``,
  `โปรเจค: ${workdir}`,
  `เป้าหมายที่รีวิว: ${scopeLine}`,
  ``,
  `📖 **อ่านมาตรฐานของบ้านนี้ก่อนเริ่ม (บังคับ)** — อยู่ในโปรเจค:`,
  `  • \`memory/CODE_REVIEW_RUBRIC.md\` — ดูอะไร (10 มิติ A–J · คะแนน 1–5 · ธงแดง · อะไรไม่ควรทัก · ฟอร์ม finding · 8 เทคนิค)`,
  `  • \`memory/CODE_REVIEW_PROCEDURE.md\` — ทำยังไง (7 พาท 28 ขั้นย่อย · คำสั่งที่ใช้ได้จริงบนเครื่องนี้ · 14 เคสจริงที่เคยหลุด)`,
  `  หาไม่เจอ → เขียนไว้ใน notCovered แล้วทำตามที่สรุปไว้ข้างล่างนี้แทน`,
  ``,
  `⛔ **Nick สั่งไว้ชัด (2026-08-17): "อย่าไปย่อ ให้ทำงานเต็มแบบที่เราออกแบบกันไว้"**`,
  `เดินให้ครบทั้ง 7 พาท ตามลำดับ ห้ามข้าม ห้ามย่อ · แต่ละขั้นย่อยมี 3 ช่อง: **ทำอะไร · จดอะไร · เสร็จเมื่อ**`,
  `ทุกอย่างที่ "จด" ต้องส่งกลับมาใน \`sheet\` — มันคือหลักฐานว่าคุณเดินจริง ไม่ใช่กระโดดไปเดา`,
  ``,
  `━━━ พาท 00 — ใบรีวิว (สร้างก่อนเปิดโค้ดบรรทัดแรก) ━━━`,
  `เปิด 6 ช่องเปล่าไว้ในหัว แล้วเติมทุกขั้น ห้ามเขียนใหม่จากความจำ:`,
  `[HEADER] [MAP] [TRACE] [Q] [DIM] [DROP]`,
  `**กฎเหล็ก: สิ่งที่ไม่ได้อยู่บนใบนี้พร้อม file:line ห้ามโผล่ใน findings**`,
  ``,
  `━━━ พาท 01 — ตั้งขอบเขต (ก่อนเปิดซอร์ส) ━━━`,
  `1.1 **ปักเป้า** เป็น ref จริง (ช่วง commit / diff / รายการ path) ห้ามเริ่มจากคำบรรยาย → sheet.header.target`,
  `    เสร็จเมื่อ: จำนวนไฟล์ที่คุณเห็นตรงกับจำนวนไฟล์ใน diff (ไม่ตรง = ดู ref ผิด แก้ก่อนไปต่อ)`,
  `1.2 **หาเจตนา** อ่านตามลำดับแล้วหยุดที่อันแรกที่ชัด: คำสั่งงาน → commit message → issue/spec → V-Log/บรรทัดขึ้นเวอร์ชัน → ชื่อเทสต์ที่เพิ่ม`,
  `    → sheet.header.intent = ประโยคเดียว "หลังแก้แล้ว X ควร Y" ที่ **พิสูจน์ผิดได้** + intentTag = STATED/INFERRED`,
  `1.3 **ไม่มีเจตนา?** ประกอบเชิงกล: (ก) สัญลักษณ์สาธารณะที่เพิ่ม+signature ที่เปลี่ยน (ข) assertion ที่เทสต์เพิ่ม (ค) ประโยคสั้นสุดที่คลุมทั้งสอง → intentTag = ASSUMED + ใส่ Q1 ใน sheet.questions`,
  `    ⛔ ห้ามรีวิวเทียบเจตนาที่เดาเองเงียบๆ — finding ที่พึ่งมันต้องเขียนแบบมีเงื่อนไข`,
  `1.4 **แยก 3 ถัง** ตามกฎไม่ใช่ความรู้สึก: IN (ไฟล์ใน diff + ไฟล์ที่มันเรียกแล้วพฤติกรรมขึ้นกับมัน) · CONTEXT (อ่านอย่างเดียว: คนเรียก, พี่น้องที่ใช้เทียบ, schema/config — **เจอบั๊กในนี้ไม่รายงาน เว้นแต่การแก้ครั้งนี้ทำให้มันผิด**) · OUT (ที่เหลือ รวมบั๊กเก่าในโค้ดที่ไม่ได้แตะ, ไฟล์ generate, lockfile)`,
  `    → sheet.header.inScope / outOfScope (พร้อมเหตุผลคำเดียว)`,
  `1.5 **ตัดเมื่อใหญ่เกิน** (>~800 บรรทัด หรือ >~15 ไฟล์ หรือ >1 ฟีเจอร์): ตัดตามลำดับ หยุดที่กฎแรกที่เข้างบ — (1) ตามความเสี่ยง เก็บ auth/เงิน/persistence/parse input ภายนอก/concurrency (2) ตามเส้นทางเรียก เก็บ 1 เส้นเต็ม (3) ของย้าย/เปลี่ยนชื่อ รีวิวบรรทัดเดียว`,
  `    → sheet.header.cutReason · ⛔ **ตัดแบบไม่ประกาศ = ข้อบกพร่องของตัวรีวิวเอง**`,
  `1.6 **ประกาศความลึก** skim/standard/deep → sheet.header.depth`,
  ``,
  `━━━ พาท 02 — ทำแผนที่ก่อนอ่าน (กว้างอย่างเดียว ยังไม่ตัดสิน) ━━━`,
  `2.1 **จุดเข้า** — หาว่าการทำงานมาถึงโค้ดนี้จากข้างนอกยังไง (main/CLI, route/handler ที่ลงทะเบียน, event, งานตามเวลา, ปุ่มใน UI, test harness) · **ค้นด้วยสำนวนการลงทะเบียนของเฟรมเวิร์ก ไม่ใช่ชื่อฟังก์ชัน** → sheet.map.entryPoints (file:line จริง ไม่ใช่เดา)`,
  `2.2 **ชั้นไฟล์** — ติดป้ายทุกไฟล์ IN ด้วยคำเดียว: view/controller/service/model/infra/util/test/config · ไฟล์ที่บอกชั้นไม่ได้ = จด Q`,
  `2.3 **ใครเรียก** — ทุกสัญลักษณ์สาธารณะที่เปลี่ยน: ค้นชื่อตรงๆ **แล้วค้นซ้ำในฐานะสตริงด้วย** (dynamic dispatch, reflection, config, template, ชื่อที่ serialize) → sheet.map.callers · N=0 ต้องเขียนว่า "โค้ดตาย หรือคนนอกใช้?"`,
  `2.4 **หาพี่น้อง** — โค้ด 1-2 ชิ้นที่ทำงานชนิดเดียวกัน (handler อื่นในโฟลเดอร์เดียวกัน, migration ก่อนหน้า, เมธอดข้างเคียง, อีกแพลตฟอร์ม, ตัวเขียน log อีกตัวที่บันทึก event ชนิดเดียวกัน) → sheet.map.siblings · ไม่มี = "none — ตัวแรกของชนิดนี้" (ยกมาตรฐาน E/H ให้สูงขึ้น)`,
  `2.5 **มีสำเนากี่ที่** — working tree / ตัวติดตั้ง / build output (dist,build) / worktree ข้างเคียง (\`*-lucifer\\\`) / **โฟลเดอร์ข้อมูลที่ dev กับ installed อาจอ่านคนละที่** → sheet.map.instances`,
  ``,
  `━━━ พาท 03 — อ่าน (ลำดับนี้เท่านั้น) ━━━`,
  `3.1 **เทสต์ก่อนโค้ด** — อ่านเฉพาะเทสต์ที่เพิ่ม/แก้ในการเปลี่ยนแปลงนี้ เขียนว่าเทสต์ *เชื่อ* ว่าอะไรคือความถูกต้อง (ยังไม่ตัดสินว่าดีไม่ดี) → Q: "เทสต์ครอบคลุม X · ไม่ครอบคลุม Y"`,
  `    เสร็จเมื่อ: เขียน "ไม่ครอบคลุม" ได้อย่างน้อย 1 ข้อ — **เขียนไม่ได้เลย = ยังอ่านไม่ละเอียดพอ**`,
  `3.2 **เดินเส้นทางเต็มเส้น (ไม่ใช่อ่าน diff)** — จากจุดเข้าใน 2.1 ไปจนถึงจุดที่มีผลจริง (เขียนดิสก์/ยิงคำสั่ง/ส่งเน็ต/ตอบผู้ใช้) จดบรรทัดละช่วง → sheet.trace`,
  `    หยุดลงลึกเมื่อ: (ก) ถึงจุดที่มีผลจริง (ข) เข้าโค้ดไลบรารีภายนอก (ค) เข้าโค้ดที่ไม่ได้แตะและสัญญาชัดเจน → จดสัญญานั้นเป็น Q แล้วเดินต่อ`,
  `    เสร็จเมื่อ: เส้นทาง **ไม่ขาดตอน** — ช่องว่างในเส้นทางคือช่องว่างในรีวิว`,
  `3.3 **ค่อยอ่าน diff** — ทีละ hunk ถามข้อเดียวต่อ hunk: **"ทำให้เจตนาใน 1.2 เป็นจริงขึ้น หรือแค่ทำให้อาการหาย"** · hunk ที่ตอบไม่ได้ → Q ทันที ห้ามข้าม`,
  `3.4 **หาสิ่งที่ไม่มี** — 5 คำถาม: (1) เทสต์ของบั๊กที่เพิ่งแก้ (2) ทาง error ของโค้ดใหม่ (3) เอกสาร/CODEMAP/V-Log (4) ทางถอย/migration (5) **ที่อื่นที่ต้องแก้แบบเดียวกัน**`,
  `    เสร็จเมื่อ: ข้อ (5) ตอบด้วย **ผลค้นหาจริง** ไม่ใช่ความรู้สึก`,
  ``,
  `━━━ พาท 04 — กวาดมิติของคุณ ━━━`,
  `${lens.pass}`,
  `ไล่ทุกมิติที่คุณรับผิดชอบให้ครบ · มิติที่ตัดทิ้งได้ต่อเมื่อบอกได้ว่า "การเปลี่ยนแปลงนี้แตะอะไรที่ทำให้มิตินี้ไม่มีความหมายเลย" → ใส่ score 0 + เหตุผล`,
  `⛔ **ห้ามเว้นมิติว่าง — ช่องว่างอ่านเหมือน "ตรวจแล้วผ่าน" ทั้งที่ไม่ได้ตรวจ**`,
  ``,
  `━━━ พาท 05 — พิสูจน์ก่อนเขียน (ทุกข้อสงสัยต้องผ่านครบ 5 ด่าน) ━━━`,
  `  1. **เปิดบรรทัดจริง** — เปิดไฟล์อ่านอีกครั้ง ห้ามอ้างจากความจำหรือจากผลค้นหา`,
  `  2. **ถูกสำเนาไหม** — ไฟล์ที่เปิดคือตัวที่รันจริง ไม่ใช่ worktree ข้างเคียง / build เก่า / โฟลเดอร์ data ของ dev *(เคยทำให้วิเคราะห์ผิดทั้งดุ้นมาแล้ว)*`,
  `  3. **เทียบพี่น้อง** — เปิดพี่น้องดูว่าเรื่องเดียวกันมันทำยังไง (อาจเป็นสำนวนปกติของโปรเจค ไม่ใช่บั๊ก)`,
  `  4. **grep ทั้ง repo** — หา pattern เดียวกันที่อื่น (บั๊กแทบไม่เคยมาตัวเดียว)`,
  `  5. **เขียนสถานการณ์ที่พังได้จริง** — input จริง → ผลผิดจริง`,
  `⛔ **ตกด่านไหนก็ตาม → ลง \`cleared\` ไม่ใช่ \`findings\`** · เขียนสถานการณ์ที่พังไม่ได้ = รสนิยม **ห้ามยื่น**`,
  `ทุก finding ต้องระบุใน gatesPassed ว่าผ่านด่านไหนบ้าง`,
  ``,
  `━━━ พาท 06 — เขียนและให้คะแนน ━━━`,
  `6.1 finding โครง 5 ช่อง: file:line · ผิดตรงไหน(1 ประโยค) · สถานการณ์ที่พัง · ความรุนแรง · ทางแก้ + **blast radius ของทางแก้นั้น**`,
  `    เสร็จเมื่อ: คนอ่านลงมือแก้ได้โดยไม่ต้องถามกลับ`,
  `6.2 คะแนนรายมิติ 1-5 (5=ส่งได้ · 4=แก้เล็กน้อย · 3=ต้องรีวิวอีกรอบ · 2=ปัญหาที่ตัวออกแบบ ต้องรื้อไม่ใช่ปะ · 1=ห้าม merge/สมมติฐานผิด)`,
  `6.3 **\`cleared\`** = ตรวจแล้วไม่ต้องแก้ · ⭐ Coddy จะเอา \`cleared\` ของคุณไปชนกับ \`findings\` ของอีกสอง lens **เพื่อให้พวกคุณตรวจทานกันเอง** — ถ้าคุณเคลียร์ไว้แต่อีกคนยื่นเป็นบั๊ก จะได้รู้ว่าใครถูก · และมันกันไม่ให้ไปแก้ของที่ไม่ต้องแก้ (= เพิ่มความเสี่ยงฟรี)`,
  `6.4 **\`notCovered\`** = สิ่งที่ไม่ได้ตรวจ + เพราะอะไร ⛔ ห้ามเว้นว่าง`,
  ``,
  `━━━ พาท 07 — ปิดงาน ━━━`,
  `7.1 (ตรวจซ้ำหลังแก้ = หน้าที่ Coddy ทีหลัง ไม่ใช่ของคุณ)`,
  `7.2 **บทเรียนข้ามโปรเจค** — ถามว่า "บั๊กแบบนี้กัดโปรเจคอื่นได้ไหม" ถ้าได้ → crossProjectLesson = อาการ → สาเหตุ → วิธีกัน (1 บรรทัด) · ไม่มีใส่ "-"`,
  ``,
  `🚫 **อะไรที่ห้ามทัก**: สไตล์ที่ formatter จัดการได้ · "ผมจะเขียนอีกแบบ" ที่บอกไม่ได้ว่าพังตอนไหน · รื้อการตัดสินใจที่มีบันทึกเหตุผลไว้แล้ว · เผื่ออนาคตที่ยังไม่มา · จุดที่พิสูจน์แล้วว่าปิดอยู่`,
  ``,
  `⛔ กฎเหล็ก (Nick #16 — เหตุ 70-agent 2026-06-13):`,
  `  • ❌ ห้ามเรียก Agent/Task tool · ❌ ห้าม spawn subagent ใดๆ — คุณรีวิว "คนเดียว"`,
  `  • ❌ ห้ามแก้/เขียน/build/run อะไรทั้งสิ้น — ใช้ **Read / Grep / Glob เท่านั้น**`,
  `  • ต้องการตัวช่วยเพิ่ม → อย่า spawn · เขียนเป็น finding ให้ Coddy แทน`,
  ``,
  `❌ ห้าม pad nit · ❌ ห้าม rubber-stamp · ไม่แน่ใจ = severity ต่ำ + บอกตรงๆ ว่ายังไม่ยืนยัน`,
].join('\n')

phase('รีวิว')

// ⛔ เป๊ะ 3 ตัว — parallel ครั้งเดียว ไม่มี fan-out ตาม finding
const reports = (await parallel(LENSES.map(lens => () =>
  agent(reviewPrompt(lens), { label:`รีวิว:${lens.key}`, phase:'รีวิว', schema: REPORT })
))).filter(Boolean)

const order = { P0:0, P1:1, P2:2, P3:3 }
const findings = reports
  .flatMap(r => (r.findings || []).map(f => ({ ...f, lens: r.lens })))
  .sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9))
const cleared = reports.flatMap(r => (r.cleared || []).map(c => ({ ...c, lens: r.lens })))
const scores  = reports.flatMap(r => (r.dimensionScores || []).map(s => ({ ...s, lens: r.lens })))

// คะแนนรวม = มิติต่ำสุด (ไม่ใช่ค่าเฉลี่ย) — กฎเหล็กของ rubric ข้อ 3 · score 0 = N/A ไม่นับ
const graded = scores.filter(s => typeof s.score === 'number' && s.score > 0)
const lowest = graded.length ? graded.reduce((a, b) => (b.score < a.score ? b : a)) : null

// ⭐ ตรวจทานกันเอง #1: lens หนึ่งยื่นเป็นบั๊ก แต่อีก lens เคลียร์ทิ้งที่ไฟล์เดียวกัน
const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '')
const fileOf = s => norm(String(s || '').split(':')[0])
const conflicts = findings.flatMap(f => cleared
  .filter(c => c.lens !== f.lens && fileOf(c.file) && fileOf(c.file) === fileOf(f.file))
  .map(c => ({ file: f.file, filedBy: f.lens, finding: f.title, clearedBy: c.lens, clearedWhat: c.what, clearedReason: c.whyNotAProblem })))

// ⭐ ตรวจทานกันเอง #2: 3 lens อ่านเจตนา/ขอบเขตตรงกันไหม (ต่างกัน = สัญญาณว่าคำสั่งงานกำกวม)
const intents = reports.map(r => ({ lens: r.lens, intent: r.sheet?.header?.intent || '(ไม่ได้ระบุ)', tag: r.sheet?.header?.intentTag || '?', target: r.sheet?.header?.target || '(ไม่ได้ระบุ)' }))
const intentAgreement = new Set(intents.map(i => norm(i.intent))).size === 1 ? 'ตรงกันทั้ง 3 lens' : '⚠️ ไม่ตรงกัน — Coddy ต้องตัดสินว่าเจตนาจริงคืออะไรก่อนเชื่อ findings'

// ⭐ ตรวจทานกันเอง #3: finding เดียวกันที่หลาย lens เจอ = ความมั่นใจสูง
const seen = {}
findings.forEach(f => { const k = fileOf(f.file); (seen[k] = seen[k] || new Set()).add(f.lens) })
const corroborated = findings.filter(f => (seen[fileOf(f.file)] || new Set()).size > 1).map(f => ({ file: f.file, title: f.title, lenses: [...seen[fileOf(f.file)]] }))

const tally = sev => findings.filter(f => f.severity === sev).length
log(`reviver เสร็จ: ${reports.length}/3 lens · findings ${findings.length} (P0:${tally('P0')} P1:${tally('P1')} P2:${tally('P2')} P3:${tally('P3')}) · cleared ${cleared.length} · ขัดกัน ${conflicts.length} · ยืนยันซ้ำ ${corroborated.length} · คะแนน ${lowest ? lowest.score : '—'} · เจตนา: ${intentAgreement}`)

return {
  agentsUsed: LENSES.length,   // = 3 เสมอ (script บังคับ ไม่มีทางเกิน)
  target: target || '(การเปลี่ยนแปลงปัจจุบัน — ดู sheets[].header.target ว่าแต่ละ lens เลือกอะไร)',
  score: lowest ? lowest.score : null,
  scoreFrom: lowest ? `${lowest.dimension} — ${lowest.why}` : 'ไม่มี lens ไหนให้คะแนน',
  intentAgreement,
  intents,
  dimensionScores: scores,
  sheets: reports.map(r => ({ lens: r.lens, ...r.sheet })),
  lenses: reports.map(r => ({ lens: r.lens, summary: r.summary, findings: (r.findings || []).length, cleared: (r.cleared || []).length, notCovered: r.notCovered, crossProjectLesson: r.crossProjectLesson })),
  findings,
  cleared,
  conflicts,
  corroborated,
  next: [
    'Coddy (ตัวหลัก) ทำต่อ 0 agent:',
    '0) ถ้า intentAgreement บอกว่าไม่ตรง → ตัดสินเจตนาจริงก่อน แล้วค่อยชั่งน้ำหนัก findings (finding ที่ตั้งบนเจตนาผิด = ตกไป)',
    '1) ⭐ ชน `conflicts` ก่อน — lens หนึ่งยื่นเป็นบั๊ก อีก lens เคลียร์ทิ้ง → **เปิดโค้ดจริงตัดสินเอง ห้ามเชื่อฝั่งใดฝั่งหนึ่งลอยๆ**',
    '2) `corroborated` (หลาย lens เจอที่เดียวกัน) = ความมั่นใจสูง · finding ที่เจอ lens เดียว = verify กับโค้ดจริงก่อนรายงาน',
    '3) เช็ค `sheets` ว่าแต่ละ lens เดินครบพาท 01-03 จริงไหม — trace ขาดตอน / callers ว่าง / instances ไม่ได้ระบุ = ผลของ lens นั้นเชื่อได้น้อยลง ต้องบอกในรายงาน',
    '4) คะแนนรวม = **มิติต่ำสุด ไม่ใช่ค่าเฉลี่ย** (คำนวณไว้ใน score/scoreFrom) — ระบุด้วยว่ามิติไหนกดคะแนน',
    '5) รายงาน: findings (ฟอร์ม 5 ช่อง) + **`cleared` = ตรวจแล้วไม่ต้องแก้** + **`notCovered` = ไม่ได้ตรวจ** — ทั้งสองอย่างต้องอยู่ในรายงาน',
    '6) `crossProjectLesson` ที่ไม่ใช่ "-" → พิจารณาเพิ่มลง memory/SHARED_LESSONS.md (#10)',
    '7) ❌ **ไม่แก้โค้ดอัตโนมัติ** — reviver = คำสั่งรีวิว · เสนอแผนแก้ + blast radius แล้วถาม Nick ก่อน เว้นแต่ Nick สั่งให้แก้เลย',
  ].join('\n'),
}
