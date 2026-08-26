export const meta = {
  name: 'reviver',
  description: 'reviver — 3 "บริษัทรีวิว" อิสระ ทำงาน **เดียวกันทั้งหมด**: แต่ละบริษัทเดินครบ 7 พาท × **ทั้ง 10 มิติ A–J** ด้วยตัวเอง แล้วให้คะแนนเต็มชุด → Coddy เอา **คะแนนและผลของ 3 บริษัทมาเทียบกัน** (ตรงกัน = เชื่อได้ · ต่างกัน = ต้องสืบว่าใครถูก) · ❌ ไม่แบ่งงานกันทำ ❌ agent ไม่แก้/ไม่ spawn ต่อ ❌ ไม่ auto-fix',
  phases: [
    { title: 'รีวิว', detail: '3 บริษัทรีวิวอิสระ · แต่ละบริษัททำงานเดียวกันครบ 7 พาท × 10 มิติ' },
  ],
}

// ───────────────────────────────────────────────────────────────────────
// command_pattern #26 · Nick 2026-08-26 (แก้จากดีไซน์เดิมที่ผิด):
//   ❌ เดิม: 3 agent แบ่งมิติกันคนละกลุ่ม (แต่ละตัวเห็นแค่ 1/3 ของงาน) → เอา finding มาต่อกัน
//   ✅ ใหม่: 3 agent = 3 "บริษัท" อิสระ **ทำงานเดียวกันทั้งหมด** ครบ 7 พาท × 10 มิติ
//           → ได้ 3 รีวิวเต็มใบ + 3 ชุดคะแนน → **เทียบกัน** = inter-rater reliability จริง
//   เหตุผล: การแบ่งงานไม่ใช่การตรวจทาน · ตรวจทานคือหลายคนทำงานเดียวกันแล้วผลตรงกันไหม
//
// เรียกผ่าน: Workflow tool { scriptPath:"<ไฟล์นี้>", args:{ workdir, target } }
// ⛔ กฎ #16: agent() ถูกเรียกแค่จุดเดียว (parallel เป๊ะ 3) · ไม่มี fan-out · agent ห้าม spawn ต่อ
// ───────────────────────────────────────────────────────────────────────

// ⚠️ args มาถึงเป็น JSON "string" ในฮาร์เนสนี้ (พิสูจน์ 2026-06-13) → parse + กัน throw · ❌ ห้ามลบ guard
let _A = args
if (typeof _A === 'string') { try { _A = JSON.parse(_A) } catch { _A = {} } }
_A = _A || {}
const workdir = _A.workdir
const target = (_A.target || '').trim()
if (!workdir)
  return { error:'reviver: ไม่มี workdir ใน args — ส่ง args เป็น object {workdir, target?}', findings:[], cleared:[], firms:[] }

const DIMENSION_LIST = 'A ความถูกต้อง · B พฤติกรรมตอนพัง · C เส้นแบ่งความเชื่อถือ · D สถานะและข้อมูล · E สัญญา/อินเทอร์เฟซ · F เทสต์ · G อ่านออก/ดูแลต่อ · H ความสอดคล้อง · I ประสิทธิภาพ · J สิ่งที่หายไป'

const REPORT = { type:'object',
  required:['firm','verdictSummary','sheet','dimensionScores','overallScore','overallScoreFrom','findings','cleared','notCovered','confidence'],
  properties:{
    firm:            { type:'string', description:'ชื่อบริษัทที่ได้รับมอบหมาย (A/B/C)' },
    verdictSummary:  { type:'string', description:'3-6 ประโยค: รีวิวอะไร เห็นอะไร สรุปว่าอย่างไร' },

    sheet: { type:'object', required:['header','map','trace','questions','questionsResolved'], properties:{
      header: { type:'object', required:['target','intent','intentTag','inScope','outOfScope','depth','cutReason'], properties:{
        target:     { type:'string', description:'1.1 ref จริงที่รีวิว' },
        intent:     { type:'string', description:'1.2 ประโยคเดียว "หลังแก้แล้ว X ควร Y" ที่พิสูจน์ผิดได้' },
        intentTag:  { type:'string', description:'STATED | INFERRED | ASSUMED' },
        inScope:    { type:'array', items:{ type:'string' } },
        outOfScope: { type:'array', items:{ type:'string' }, description:'พร้อมเหตุผลคำเดียวต่ออัน' },
        depth:      { type:'string', description:'skim | standard | deep' },
        cutReason:  { type:'string', description:'ตัดอะไรทิ้งเพราะกฎไหน · ไม่ได้ตัด = "ไม่ได้ตัด"' },
      } },
      map: { type:'object', required:['entryPoints','layers','callers','siblings','instances'], properties:{
        entryPoints:{ type:'array', items:{ type:'string' }, description:'2.1 file:line → ชื่อ' },
        layers:     { type:'array', items:{ type:'string' }, description:'2.2 path = view|controller|service|model|infra|util|test|config' },
        callers:    { type:'array', items:{ type:'string' }, description:'2.3 symbol: file:line,... (N) · N=0 ต้องระบุว่าโค้ดตายหรือคนนอกใช้' },
        siblings:   { type:'array', items:{ type:'string' }, description:'2.4 path:line — เป็นคู่ของอะไร' },
        instances:  { type:'string', description:'2.5 dev vs installed/build vs worktree — อ่านตัวไหนอยู่' },
      } },
      trace:            { type:'array', items:{ type:'string' }, description:'3.2 file:line → file:line — ห้ามขาดตอน' },
      questions:        { type:'array', items:{ type:'string' }, description:'[Q] คำถามค้างที่ตั้งไว้ระหว่างทาง' },
      questionsResolved:{ type:'array', items:{ type:'string' }, description:'05.0 ทุก Q ต้องมีสถานะ: verified | became finding Fn | UNRESOLVED' },
    } },

    dimensionScores:{ type:'array', description:'⛔ ต้องครบ **ทั้ง 10 มิติ A–J** ไม่มีข้อยกเว้น (ไม่เกี่ยว = score 0 + เหตุผล)', items:{ type:'object',
      required:['dimension','score','why','evidence'], properties:{
        dimension:{ type:'string', description:'ตัวอักษร A-J + ชื่อมิติ' },
        score:    { type:'number', description:'1-5 · 0 = N/A' },
        why:      { type:'string', description:'อะไรกดคะแนน หรือทำไม N/A' },
        evidence: { type:'string', description:'ตรวจอะไรถึงให้คะแนนนี้ (file:line หรือคำสั่งที่รัน) — ห้ามให้คะแนนลอยๆ' },
      } } },
    overallScore:    { type:'number', description:'= **มิติต่ำสุดที่ไม่ใช่ 0** ห้ามเฉลี่ย' },
    overallScoreFrom:{ type:'string', description:'มิติไหนกดคะแนน + เพราะอะไร' },

    findings:{ type:'array', items:{ type:'object',
      required:['severity','title','file','dimension','problem','failureScenario','evidence','gatesPassed','suggestedFix','blastRadius'], properties:{
        severity:       { type:'string', enum:['BLOCKER','MAJOR','MINOR'] },
        title:          { type:'string' },
        file:           { type:'string', description:'path:line @ <sha ถ้ารู้> — บังคับ · ถ้าเป็นของที่ "ขาดหายไป" ให้ใส่ absence anchor (path ที่ควรมีแต่ไม่มี)' },
        dimension:      { type:'string', description:'มิติ A-J' },
        problem:        { type:'string', description:'ผิดตรงไหน 1 ประโยค' },
        failureScenario:{ type:'string', description:'input จริง → ผลผิดจริง · ⛔ เขียนไม่ได้ = ห้ามยื่น' },
        evidence:       { type:'string' },
        gatesPassed:    { type:'string', description:'ผ่านด่าน 1/2/5 อย่างไร + ผลของด่าน 3/4 (ขยายขอบเขตไหม)' },
        suggestedFix:   { type:'string' },
        blastRadius:    { type:'string', description:'แก้แล้วกระทบอะไร' },
      } } },

    cleared:{ type:'array', description:'[DROP] ที่ดูน่าสงสัยแต่ตรวจแล้วไม่ใช่ปัญหา — ⭐ ใช้เทียบข้ามบริษัท', items:{ type:'object',
      required:['what','file','whyNotAProblem'], properties:{
        what:{ type:'string' }, file:{ type:'string' }, whyNotAProblem:{ type:'string' },
      } } },

    notCovered:{ type:'string', description:'สิ่งที่ไม่ได้ตรวจ + เพราะอะไร (รวม UNRESOLVED Q) ⛔ ห้ามเว้นว่าง' },
    confidence:{ type:'string', description:'สูง/กลาง/ต่ำ + เพราะอะไร — เดินครบทุกพาทไหม มีอะไรที่เข้าไม่ถึง' },
    crossProjectLesson:{ type:'string', description:'บั๊กชนิดนี้กัดโปรเจคอื่นได้ไหม: อาการ → สาเหตุ → วิธีกัน · ไม่มีใส่ "-"' },
  } }

const scopeLine = target
  ? `**${target}**`
  : `**การเปลี่ยนแปลงปัจจุบันของโปรเจค** — หาเองจาก git (uncommitted diff ก่อน · tree สะอาด → commit ล่าสุด) แล้วเขียนใน sheet.header.target ว่าคุณเลือกอะไร`

// ── คำสั่งเต็ม: หลักการทุกข้อถูกสอนไว้ในนี้ (Nick 2026-08-26: "สอนมันไว้ในคำสั่งเลย ไม่ใช่ล๊วกๆ") ──
const buildPrompt = (firm) => [
  `คุณคือ **บริษัทรีวิวโค้ด "${firm}"** — หนึ่งใน 3 บริษัทที่ Nick จ้างมาพร้อมกัน`,
  ``,
  `⚠️ **สำคัญที่สุด — เข้าใจบทบาทให้ถูก:**`,
  `ทั้ง 3 บริษัทได้รับ **งานเดียวกันทุกประการ** และต้องทำ **ครบทั้งหมดด้วยตัวเอง** —`,
  `❌ ไม่มีการแบ่งงานกันทำ · ❌ ไม่มี "ส่วนของฉัน/ส่วนของเขา" · ❌ ห้ามคิดว่าเดี๋ยวบริษัทอื่นตรวจให้`,
  `คุณต้องเดินครบ **ทั้ง 7 พาท** และให้คะแนน **ครบทั้ง 10 มิติ A–J** ด้วยตัวคุณเอง`,
  `Nick จะเอา **ผลของ 3 บริษัทมาเทียบกัน** — ถ้าตรงกันแปลว่าเชื่อถือได้ · ถ้าต่างกันเขาจะสืบว่าใครทำงานหลุด`,
  `**บริษัทที่ตรวจไม่ครบจะถูกจับได้ทันที** เพราะอีก 2 บริษัทเจอสิ่งที่คุณไม่เจอ`,
  ``,
  `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  `โปรเจค: ${workdir}`,
  `เป้าหมายที่รีวิว: ${scopeLine}`,
  `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  ``,
  `📖 **อ่านมาตรฐานฉบับเต็มก่อนเริ่ม (บังคับ — มีอยู่ในโปรเจค):**`,
  `  • \`memory/CODE_REVIEW_RUBRIC.md\` — ดูอะไร`,
  `  • \`memory/CODE_REVIEW_PROCEDURE.md\` — ทำยังไง`,
  `  หาไม่เจอ → เขียนใน notCovered แล้วใช้คำสั่งฉบับนี้แทน (ข้างล่างนี้คือสาระครบถ้วนแล้ว)`,
  ``,
  `╔══════════════════════════════════════════╗`,
  `║  หัวใจของการรีวิว — จำ 2 ข้อนี้ให้ขึ้นใจ  ║`,
  `╚══════════════════════════════════════════╝`,
  `นักรีวิวมือใหม่ตรวจว่า "โค้ดเขียนสวยไหม" — **นักรีวิวจริงตรวจ 2 อย่าง:**`,
  `  ① **มันทำสิ่งที่มันอ้างว่าทำจริงไหม**`,
  `  ② **ถ้ามันไม่ทำ จะเกิดอะไรขึ้น**`,
  `ข้อ ② สำคัญกว่าและเป็นข้อที่คนมองข้ามที่สุด — บั๊กที่ทำให้ระบบพังจริงเกือบทั้งหมดอยู่บน "ทางที่ผิดพลาด" ไม่ใช่ทางปกติ`,
  ``,
  `═══ พาท 00 — ใบรีวิว (สร้างก่อนเปิดโค้ดบรรทัดแรก) ═══`,
  `เปิด 6 ช่องไว้แล้วเติมทุกขั้น **ห้ามเขียนย้อนหลังจากความจำ**: [HEADER] [MAP] [TRACE] [Q] [DIM] [DROP]`,
  `**กฎเหล็ก:** สิ่งที่ไม่ได้อยู่บนใบนี้พร้อม \`file:line\` **หรือ absence anchor** (path ที่ควรมีของแต่ไม่มี) — ห้ามโผล่ในรายงาน`,
  `*(absence anchor มีไว้เพราะ finding มิติ J คือ "ของที่หายไป" ซึ่งไม่มีบรรทัดเป็นของตัวเอง)*`,
  ``,
  `═══ พาท 01 — ตั้งขอบเขต (ก่อนเปิดซอร์ส · ~10% ของเวลา) ═══`,
  `**1.1 ปักเป้าเป็น ref จริง** — ช่วง commit / diff / รายการ path · ❌ ห้ามเริ่มจากคำบรรยายเป็นข้อความ`,
  `   เสร็จเมื่อ: จำนวนไฟล์ที่คุณเห็น **ตรงกับ** จำนวนไฟล์ใน diff — ไม่ตรง = คุณดู ref ผิด ต้องแก้ก่อนไปต่อ`,
  `**1.2 หาเจตนา** — อ่านตามลำดับ **หยุดที่อันแรกที่ให้คำตอบชัด**: คำสั่งงาน → commit message → issue/spec → V-Log/บรรทัดขึ้นเวอร์ชัน → ชื่อเทสต์ที่เพิ่ม`,
  `   เขียนประโยคเดียว "หลังแก้แล้ว X ควร Y" ที่ **พิสูจน์ผิดได้** (ชี้บรรทัดแล้วบอกได้ว่า "ตรงนี้ทำไม่ได้ตามนั้น")`,
  `**1.3 ถ้าไม่มีใครบอกเจตนา** — ประกอบเชิงกล: (ก) สัญลักษณ์สาธารณะที่เพิ่ม + signature ที่เปลี่ยน (ข) assertion ที่เทสต์เพิ่ม (ค) ประโยคสั้นสุดที่คลุมทั้งสองลิสต์ → ติดป้าย ASSUMED + ตั้ง Q1`,
  `   ⛔ **ห้ามรีวิวเทียบเจตนาที่เดาเองเงียบๆ** — finding ที่พึ่งเจตนาสมมติ ต้องเขียนแบบมีเงื่อนไข ("ถ้าเจตนาคือ X แล้ว...")`,
  `**1.4 แยก 3 ถัง ตามกฎ ไม่ใช่ความรู้สึก** *(ชั่วคราว — เติมได้เมื่อพาท 02 เผยคนเรียก/พี่น้อง)*`,
  `   • **IN** = ไฟล์ใน diff + ไฟล์ที่ diff เรียกเข้าไปแล้วพฤติกรรมขึ้นกับมัน`,
  `   • **CONTEXT** = อ่านอย่างเดียว (คนเรียก, พี่น้องที่ใช้เทียบ, schema/config) — **เจอบั๊กในนี้ไม่รายงาน เว้นแต่การแก้ครั้งนี้ทำให้มันผิด**`,
  `   • **OUT** = ที่เหลือ รวม**บั๊กเก่าในโค้ดที่ไม่ได้แตะ**, ไฟล์เปลี่ยนแค่ฟอร์แมต, ไฟล์ generate, lockfile, โค้ดคนอื่น`,
  `**1.5 ตัดเมื่อใหญ่เกิน** (>~800 บรรทัด หรือ >~15 ไฟล์ หรือ >1 ฟีเจอร์) — ตัดตามลำดับ **หยุดที่กฎแรกที่เข้างบ**:`,
  `   (1) **ตามความเสี่ยง** เก็บที่แตะ auth/สิทธิ์, เงิน/ปริมาณ, การเขียนถาวร/migration, การแปลง input ภายนอก, งานพร้อมกัน`,
  `   (2) **ตามเส้นทางเรียก** เก็บ 1 เส้นเต็มจากจุดเข้าถึงจุดที่มีผล ตัดเส้นขนานที่โครงเหมือนกัน`,
  `   (3) **ของย้าย/เปลี่ยนชื่อ** รีวิวบรรทัดเดียวพอ ไม่ต้องอ่าน`,
  `   ⛔ **ตัดแบบไม่ประกาศ = ข้อบกพร่องของตัวรีวิวเอง** ต้องเขียน cutReason เสมอ`,
  `**1.6 ประกาศความลึก** skim/standard/deep + เพดานเวลา · ถึงเพดาน = **หยุดแล้วรายงานว่าครอบคลุมถึงไหน** ไม่ยืดเงียบๆ`,
  `   *(ถ้าจะใช้ 1.5 ให้ทำ 1.6 ก่อน เพราะการตัดต้องตัดเทียบกับงบ)*`,
  ``,
  `═══ พาท 02 — ทำแผนที่ก่อนอ่าน (กว้างอย่างเดียว ยังไม่ตัดสิน · ~10%) ═══`,
  `**2.1 จุดเข้า** — การทำงานมาถึงโค้ดนี้จากข้างนอกยังไง: main/CLI, route/handler ที่ลงทะเบียน, ตัวรับ event, งานตามเวลา, การผูกปุ่มใน UI, test harness`,
  `   **ค้นด้วยสำนวนการลงทะเบียนของเฟรมเวิร์ก ไม่ใช่ชื่อฟังก์ชัน** → ต้องได้ file:line จริง ไม่ใช่เดา`,
  `**2.2 ชั้นของไฟล์** — ติดป้ายทุกไฟล์ IN คำเดียว: view|controller|service|model|infra|util|test|config · **ไฟล์ที่บอกชั้นไม่ได้ = finding ในตัวมันเอง** จดเป็น Q`,
  `**2.3 ใครเรียก** — ทุกสัญลักษณ์สาธารณะที่เปลี่ยน (ฟังก์ชัน คลาส ค่าคงที่ คีย์ config route ฟิลด์ schema):`,
  `   ค้นชื่อตรงๆ **แล้วค้นซ้ำในฐานะ "สตริง" ด้วย** — dynamic dispatch, reflection, config, template, ชื่อที่ถูก serialize`,
  `   N=0 → เขียน "โค้ดตาย หรือคนนอกใช้?" · **ค้นแค่ชื่อไม่พอ ต้องค้นแบบสตริงแล้วด้วย**`,
  `**2.4 หาพี่น้อง** — โค้ด 1-2 ชิ้นที่ทำ **งานชนิดเดียวกัน**: handler ตัวอื่นในโฟลเดอร์เดียวกัน, migration ก่อนหน้า, เมธอดข้างเคียงใน service, การทำงานเดียวกันบนอีกแพลตฟอร์ม, **ตัวเขียน log อีกตัวที่บันทึก event ชนิดเดียวกัน**`,
  `   ไม่มี → เขียน "none — ตัวแรกของชนิดนี้" ซึ่ง **ยกมาตรฐานมิติ E/H ให้สูงขึ้น**`,
  `**2.5 มีสำเนากี่ที่** — working tree / ตัวติดตั้งแล้ว / build output (dist,build) / **worktree ข้างเคียง (\`*-lucifer\\\`)** / **โฟลเดอร์ข้อมูลที่ dev กับ installed อาจอ่านคนละที่**`,
  `   เสร็จเมื่อ: รู้แน่ว่ากำลังอ่านสำเนาไหน และ runtime อ่านตัวไหน`,
  ``,
  `═══ พาท 03 — อ่าน (ลำดับนี้เท่านั้น · ~30%) ═══`,
  `**3.1 อ่านเทสต์ก่อนโค้ด** — เฉพาะเทสต์ที่เพิ่ม/แก้ในการเปลี่ยนแปลงนี้ · เขียนว่าเทสต์ *เชื่อ* ว่าอะไรคือความถูกต้อง (ยังไม่ตัดสินว่าดีไม่ดี)`,
  `   เสร็จเมื่อ: เขียน "สิ่งที่เทสต์ไม่ครอบคลุม" ได้อย่างน้อย 1 ข้อ — **เขียนไม่ได้เลย = ยังอ่านไม่ละเอียดพอ**`,
  `**3.2 เดินเส้นทางเต็มเส้น (ไม่ใช่อ่าน diff)** — จากจุดเข้าใน 2.1 ถึง **จุดที่มีผลจริง** (เขียนดิสก์ / ยิงคำสั่ง / ส่งเน็ต / ตอบผู้ใช้) จดบรรทัดละช่วง`,
  `   หยุดลงลึกเมื่อ: (ก) ถึงจุดที่มีผลจริง (ข) เข้าไลบรารีภายนอก (ค) เข้าโค้ดที่ไม่ได้แตะ **และสัญญาชัดเจน** → จดสัญญานั้นเป็น Q แล้วเดินต่อ`,
  `   เสร็จเมื่อ: เส้นทาง **ไม่ขาดตอน** — ช่องว่างในเส้นทาง คือช่องว่างในรีวิว`,
  `**3.3 ค่อยอ่าน diff** — ทีละ hunk ถามข้อเดียว: **"ทำให้เจตนาใน 1.2 เป็นจริงขึ้น หรือแค่ทำให้อาการหาย"** · hunk ที่ตอบไม่ได้ → Q ทันที **ห้ามผ่านตาไปเฉยๆ**`,
  `**3.4 หาสิ่งที่ไม่มี** (ยากสุด ได้ผลสุด) — 5 คำถาม: (1) เทสต์ของบั๊กที่เพิ่งแก้ (2) ทาง error ของโค้ดใหม่ (3) เอกสาร/CODEMAP/V-Log (4) ทางถอย/migration (5) **ที่อื่นที่ต้องแก้แบบเดียวกัน**`,
  `   เสร็จเมื่อ: ข้อ (5) ตอบด้วย **ผลค้นหาจริง** ไม่ใช่ความรู้สึก`,
  ``,
  `═══ พาท 04 — กวาดให้ครบ 10 มิติ (~25%) ═══`,
  `⛔ **คุณรับผิดชอบทั้ง 10 มิติ ไม่ใช่บางมิติ** · จัดกลุ่มเป็น 4 รอบเพื่อไม่ให้หลุดบริบท (ไม่ใช่ 10 รอบ):`,
  ``,
  `**รอบ 1 — ตรรกะ (มิติ A + D) · อ่านช้าทีละบรรทัดบนเส้นทางใน [TRACE]**`,
  `  A ความถูกต้อง: ชื่อ/docstring ตรงพฤติกรรมจริงไหม (**ชื่อที่โกหก = บั๊กในตัวมันเอง**) · ค่าขอบ 0/1/ว่าง/null/ติดลบ/ค่าสูงสุด/**ค่าซ้ำ** · off-by-one ใน loop และ slice · ตัวเลข: ปัดเศษ, float กับเงิน, หารศูนย์ · เวลา: timezone, DST, **นาฬิกาเดินถอยหลัง**, wall clock vs monotonic · encoding: UTF-8/BOM/cp1252 · **รันซ้ำได้ไหม (idempotent)** — กดสองครั้ง/retry/ข้อความมาซ้ำ`,
  `  D สถานะและข้อมูล: ใครเป็นเจ้าของ state นี้ — แหล่งเดียวหรือซ้ำหลายที่ (**grep ทุกจุดที่เขียนค่ามัน · คอมเมนต์ที่ระบุเจ้าของไม่ใช่หลักฐาน grep ต่างหากที่ใช่**) · รอดรีสตาร์ท/ไฟดับกลางคันไหม · ข้อมูลเก่า/เวอร์ชันเก่าเกิดอะไรขึ้น (migration) · **cache key ผูกกับอะไร**`,
  ``,
  `**รอบ 2 — ทางที่พัง (มิติ B + C) · สองสวีป**`,
  `  (ก) อ่าน **เฉพาะ** \`if\` / \`try\` / \`return\` ก่อนกำหนด — ข้ามทางปกติทั้งหมด`,
  `  (ข) **แล้วเดินทางปกติใน [TRACE] อีกรอบ ถามข้อเดียว: "ตรงไหนควรมีการตรวจสอบแต่ไม่มี"**`,
  `      ← จำเป็น เพราะ **fail-open ไม่มีกิ่งให้อ่าน** สวีป (ก) มองไม่เห็น`,
  `  B พฤติกรรมตอนพัง: **fail-open หรือ fail-closed** — เมื่อการตรวจสอบทำงานไม่ได้ มันปล่อยผ่านหรือปฏิเสธ (**ช่องที่พบบ่อยที่สุด**) · error ถูกกลืนเงียบไหม (\`except: pass\`) · **ผู้ใช้เห็นความล้มเหลวไหม — log อย่างเดียวไม่นับ** · พังกลางทาง state ค้างครึ่ง ไม่มี rollback · retry วนไม่รู้จบ / retry สิ่งที่ retry ไม่ได้ · cleanup บนทาง error (ไฟล์ ล็อก ซ็อกเก็ต เธรด)`,
  `  C เส้นแบ่งความเชื่อถือ: ข้อมูลข้ามจากไม่เชื่อถือมาเชื่อถือตรงไหน · **ตัวตนอ่านจากช่องทางที่ตรวจแล้ว หรือจาก payload** · จุดฉีด SQL/shell string/innerHTML/path traversal · สิทธิ์เช็คถูกชั้นไหม มีทางเข้าอื่นเลี่ยงได้ไหม · **มีอะไร self-elevate สิทธิ์ตัวเองไหม**`,
  ``,
  `**รอบ 3 — เทียบ (มิติ H + E) · เปิดไฟล์พี่น้องจาก 2.4 ไว้ข้างกันแล้วไล่ต่างทีละจุด**`,
  `  H ความสอดคล้อง ⭐: **สองตัวทำงานชนิดเดียวกัน ตัวหนึ่งมียามอีกตัวไม่มี = ตัวใดตัวหนึ่งผิดเสมอ** (วิธีหาบั๊กที่เร็วที่สุดโดยไม่ต้องเข้าใจทั้งระบบ) · ตรรกะที่เคยซ้ำกันแล้วแยกทาง ตัวหนึ่งได้ fix อีกตัวไม่ได้`,
  `  E สัญญา: ของเก่ายังใช้ได้ไหม (client/ไฟล์/firmware เก่า) · **ค่า default เป็นตัวเลือกที่ปลอดภัยไหม** (ระบบความปลอดภัยที่ต้องเปิดเอง = ระบบที่ปิดอยู่) · API ใช้ผิดง่ายไหม (bool ลอยๆ, ลำดับ arg ที่สลับได้)`,
  ``,
  `**รอบ 4 — รอบนอก (มิติ F + G + I + J) · กวาดเร็ว ใช้ grep/linter มากกว่าสายตา**`,
  `  F เทสต์: เทสพฤติกรรมหรือเทสวิธีเขียน · **ถ้าย้อนโค้ดที่แก้ออก เทสต์ต้องแดง — ยังเขียว = เทสต์ไร้ค่า** · ทางที่ผิดพลาดถูกเทสไหม · **เทสต์ assert "ข้อความในไฟล์" แทนพฤติกรรมไหม** (ถามว่า "ถ้าลบโค้ดเหลือแต่คอมเมนต์ เทสต์ยังเขียวไหม") · เทสต์แตะสโตร์จริง/ยิง API จริง/สร้างเธรดค้างไหม`,
  `  G อ่านออก: คอมเมนต์อธิบาย **ทำไม** ไม่ใช่ *อะไร* · เข้าสำนวนโค้ดรอบข้าง · โค้ดตาย/TODO ค้าง/debug print`,
  `  I ประสิทธิภาพ: ทักเฉพาะที่มีผลจริง **แต่ของที่ไม่มีขอบเขตทักได้เสมอ** · query ใน loop · งานหนักใต้ล็อก · เรียก API ช้าบนเธรด UI`,
  `  J สิ่งที่หายไป: เทสต์ของบั๊กที่เพิ่งแก้ · เอกสาร/CODEMAP/V-Log · ทางถอย/migration · **ที่อื่นที่ต้องแก้แบบเดียวกัน (grep pattern เดิม)**`,
  ``,
  `  🚩 **ธงแดง — เห็นเมื่อไหร่หยุดดู 2 นาที:** การตรวจสอบที่ข้ามได้เมื่อไม่มีข้อมูล (ไม่มี hash → ติดตั้งเลย) · ประกอบคำสั่งด้วยการต่อสตริง (shell/SQL/HTML) · **เรียกโปรแกรมด้วยชื่อเปล่าไม่ใส่ path เต็ม** · ตัวตนอ่านจาก payload · ค่า default ที่ปล่อยผ่าน · \`except: pass\` · คอมเมนต์ว่า "อันนี้ไม่มีทางเกิด" · ฟังก์ชันที่เปลี่ยนจากทำ 1 อย่างเป็น 2 อย่าง`,
  ``,
  `  ⛔ **ห้ามเว้นมิติว่าง** — ตัดมิติได้ต่อเมื่อบอกได้ว่า "การเปลี่ยนแปลงนี้แตะอะไรที่ทำให้มิตินี้ไม่มีความหมายเลย" → score 0 + เหตุผล · **ช่องว่างอ่านเหมือน "ตรวจแล้วผ่าน" ทั้งที่ไม่ได้ตรวจ**`,
  ``,
  `═══ พาท 05 — พิสูจน์ก่อนเขียน (~15%) ═══`,
  `**05.0 ปิด [Q] ให้หมดก่อน** — ทุกคำถามค้างต้องมีสถานะปลายทาง: \`verified\` | \`became finding Fn\` | \`UNRESOLVED\``,
  `   *(สัญญาของโค้ดที่คุณเลือกไม่ลงลึกใน 3.2 ต้องมาเช็คตรงนี้ — บั๊กจริงเคยซ่อนอยู่ในสัญญาพวกนี้)*`,
  ``,
  `**ด่านทิ้ง (drop gates) — ตกด่านนี้ = ข้อสงสัยไม่จริง → ลง \`cleared\`:**`,
  `  1. **เปิดบรรทัดจริง** — เปิดไฟล์อ่านอีกครั้งด้วยตา ห้ามอ้างจากความจำหรือจากผลค้นหา · **จด \`path:line @ sha\`** เพราะเลขบรรทัดเน่าเร็ว`,
  `  2. **ถูกสำเนาไหม** — ไฟล์ที่เปิดคือตัวที่รันจริง ไม่ใช่ worktree ข้างเคียง / build เก่า / โฟลเดอร์ data ของ dev · **ตกด่านนี้ = วิเคราะห์ผิดทั้งดุ้น**`,
  `  5. **เขียนสถานการณ์ที่พังได้จริง** — input จริง → ผลผิดจริง · **เขียนไม่ได้ = รสนิยม ไม่ใช่ finding ห้ามยื่น**`,
  ``,
  `**ด่านขยาย (expand gates) — ตกด่านนี้ finding ยิ่ง "ใหญ่ขึ้น" ไม่ใช่หายไป:**`,
  `  3. **เทียบพี่น้อง** — พี่น้องมียาม → finding ยืน (มิติ H) · **พี่น้องมีรูเหมือนกัน → เป็นบั๊กเชิงระบบ ไม่ใช่สำนวนปกติ** ขยายเป็นทั้งสองจุด`,
  `  4. **grep ทั้ง repo** — เจอที่อื่นด้วย → finding เป็นแบบหลายจุด ลิสต์ให้ครบ`,
  `  ⛔ **ห้ามทิ้ง finding เพราะตกด่าน 3 หรือ 4 เด็ดขาด** — "พี่น้องก็เป็นเหมือนกัน" คือหลักฐานว่าเป็นปัญหาเชิงระบบ ไม่ใช่ข้อแก้ตัว`,
  ``,
  `═══ พาท 06 — เขียนและให้คะแนน (~10%) ═══`,
  `**6.1 ฟอร์ม finding 5 ช่อง:** \`file:line\` · ผิดตรงไหน (1 ประโยค) · **สถานการณ์ที่พัง (input → ผล)** · ความรุนแรง · ทางแก้ + **blast radius ของทางแก้นั้น**`,
  `   ความรุนแรง: **BLOCKER** = ห้าม merge (กดคะแนนรวม ≤2) · **MAJOR** = ต้องแก้ก่อนส่ง (คะแนนไม่เกิน 3) · **MINOR** = ควรแก้แต่ไม่กั้นการส่ง`,
  `   เสร็จเมื่อ: **คนอ่านลงมือแก้ได้โดยไม่ต้องถามกลับ**`,
  `**6.2 คะแนน 1–5 รายมิติ ครบทั้ง 10:**`,
  `   5 = ส่งได้เลย (ทำตามที่อ้าง · ทางพังถูกจัดการ **และผู้ใช้เห็น** · เทสต์ตรึงพฤติกรรม · ไม่มีที่อื่นค้าง)`,
  `   4 = ผ่านหลังแก้เล็กน้อย (ถูกต้อง แต่มีช่องว่าง — เทสต์ขาด 1 ตัว, ชื่อกำกวม, fail-open จุดเล็ก)`,
  `   3 = ต้องรีวิวอีกรอบ (happy path ใช้ได้ แต่มีกรณีผิดพลาดจริงที่ยังไม่จัดการ หรือเส้นแบ่งความเชื่อถือหลวม)`,
  `   2 = ปัญหาที่ตัวออกแบบ (โค้ดถูกแต่วางรูปทรงผิด — ต้องรื้อ ไม่ใช่ปะ)`,
  `   1 = ห้าม merge (ทำของเดิมพัง หรือ **สมมติฐานตั้งต้นผิด** — ยิ่งตรรกะเนียนยิ่งอันตราย)`,
  `   **คะแนนรวม = มิติที่ต่ำที่สุด ห้ามเฉลี่ยเด็ดขาด** — ช่องโหว่ 1 จุดไม่ถูกหักล้างด้วยโค้ดสวยอีก 9 จุด · ระบุว่ามิติไหนกดคะแนน`,
  `**6.3 \`cleared\`** = ตรวจแล้วไม่ต้องแก้ — **มีค่าเท่ากับของที่เจอ** เพราะกันไม่ให้ใครไปแก้ของที่ไม่ต้องแก้ (= เพิ่มความเสี่ยงฟรี) และกันรอบหน้าเสียเวลาซ้ำ`,
  `**6.4 \`notCovered\`** = สิ่งที่ไม่ได้ตรวจ + เพราะอะไร (รวม out-of-scope + ที่ตัดทิ้ง + มิติ N/A + **ทุก Q ที่ UNRESOLVED**) ⛔ ห้ามเว้นว่าง`,
  ``,
  `═══ พาท 07 — ปิดงาน ═══`,
  `**7.1** (ตรวจซ้ำหลังแก้ = หน้าที่ Coddy ทีหลัง ไม่ใช่ของคุณ)`,
  `**7.2 บทเรียนข้ามโปรเจค** — "บั๊กแบบนี้กัดโปรเจคอื่นได้ไหม" ถ้าได้ → crossProjectLesson = อาการ → สาเหตุ → วิธีกัน (1 บรรทัด) · ไม่มีใส่ "-"`,
  ``,
  `═══ ⚠️ ถ้าโค้ดนี้เขียนโดย AI/ซีซั่นเดียวกับที่รีวิว (ปกติของที่นี่) ═══`,
  `  • **หาเจตนาจากคำสั่งงานของ Nick เท่านั้น ห้ามจาก commit message ของตัวเอง** (commit บอกว่า "ทำอะไร" ไม่ใช่ "ต้องการอะไร" — รีวิวเทียบสรุปตัวเองได้แต่คำตอบว่า "ตรงกัน")`,
  `  • **เปิดไฟล์ใหม่ทุกไฟล์** อย่ารีวิวจากการแก้ที่จำได้ (สิ่งที่จำได้คือสิ่งที่ตั้งใจ ไม่ใช่ไบต์บนดิสก์)`,
  `  • **ด่าน 2 ไม่ใช่ทางเลือก** — ยืนยันว่าอินสแตนซ์ไหนรันจริง`,
  ``,
  `═══ 🚫 อะไรที่ห้ามทัก (วินัยสำคัญพอๆ กับการหาเจอ) ═══`,
  `รีวิวที่มี 40 ข้อโดย 35 ข้อเป็นรสนิยม **ทำให้อีก 5 ข้อที่สำคัญถูกมองข้าม**`,
  `  ❌ สไตล์ที่ formatter จัดการได้ (เว้นวรรค ขึ้นบรรทัด) · ❌ "ผมจะเขียนอีกแบบ" ที่บอกไม่ได้ว่าพังตอนไหน`,
  `  ❌ รื้อการตัดสินใจที่มีบันทึกเหตุผลไว้แล้ว (ต้องมีข้อมูลใหม่ถึงรื้อ) · ❌ เผื่ออนาคตที่ยังไม่มา · ❌ จุดที่พิสูจน์แล้วว่าปิดอยู่`,
  `  **กฎเดียวที่คัดกรองได้หมด: ทุก finding ต้องระบุสถานการณ์ที่พังได้จริง input → ผลผิด เขียนไม่ได้ อย่าทัก**`,
  ``,
  `═══ 🔧 8 เทคนิคที่หาบั๊กได้เร็วที่สุด (ใช้ให้ครบ) ═══`,
  `  1. **เทียบฟังก์ชันพี่น้อง** — ตัวหนึ่งมียาม อีกตัวไม่มี = ตัวใดตัวหนึ่งผิดเสมอ`,
  `  2. **ตามข้อมูลจากต้นทางที่ไม่เชื่อถือถึงปลายทางที่มีผล** — จุดที่มันเปลี่ยนจาก "ข้อมูล" เป็น "คำสั่ง" คือจุดที่ต้องมียาม`,
  `  3. **ถามว่า "ถ้ารันสองครั้ง / พร้อมกัน / หลังรีสตาร์ท"** — สามคำถามนี้จับบั๊ก state ได้เกินครึ่ง`,
  `  4. **ล่า fail-open** — หา \`if\` ทุกตัวที่ "ไม่มีข้อมูล" แปลว่า "ผ่าน"`,
  `  5. **อ่านเทสต์ก่อนแล้วมองหาช่องว่าง** — สิ่งที่เขาไม่ได้เทส คือสิ่งที่เขาไม่ได้คิดถึง`,
  `  6. **grep หา pattern เดียวกันที่อื่น** — บั๊กแทบไม่เคยมาตัวเดียว`,
  `  7. **เทียบชื่อกับพฤติกรรม** — \`get_\` ที่เขียนข้อมูล, \`verify_\` ที่คืน true เมื่อไม่มีอะไรให้ตรวจ`,
  `  8. ⭐ **ค้านที่สมมติฐาน ไม่ใช่แค่ตรรกะ** — ตรรกะอาจถูกทั้งหมดแต่ตั้งอยู่บนสิ่งที่ไม่จริง ถามเสมอ: "ประโยคที่โค้ดนี้เชื่อ ยังจริงอยู่ไหม"`,
  ``,
  `═══ ⛔ กฎเหล็ก (Nick #16 — เหตุ 70-agent 2026-06-13) ═══`,
  `  • ❌ **ห้ามเรียก Agent/Task tool · ห้าม spawn subagent ใดๆ** — คุณทำงานคนเดียวทั้งบริษัท`,
  `  • ❌ **ห้ามแก้/เขียน/build/run อะไรทั้งสิ้น** — ใช้ **Read / Grep / Glob เท่านั้น**`,
  `  • ต้องการตัวช่วยเพิ่ม → อย่า spawn · เขียนเป็น finding ให้ Coddy แทน`,
  ``,
  `❌ ห้าม pad nit · ❌ ห้าม rubber-stamp · ไม่แน่ใจ = severity ต่ำ + บอกตรงๆ ว่ายังไม่ยืนยัน`,
  `⛔ **dimensionScores ต้องครบ 10 มิติ** (${DIMENSION_LIST}) · **notCovered และ confidence ห้ามเว้นว่าง**`,
].join('\n')

phase('รีวิว')

// ⛔ เป๊ะ 3 บริษัท — parallel ครั้งเดียว ไม่มี fan-out · ทุกบริษัทได้ prompt "เหมือนกันทุกประการ" ต่างแค่ชื่อ
const FIRMS = ['A', 'B', 'C']
const reports = (await parallel(FIRMS.map(f => () =>
  agent(buildPrompt(f), { label:`บริษัท ${f}`, phase:'รีวิว', schema: REPORT })
))).filter(Boolean)

const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '')
const sev  = { BLOCKER:0, MAJOR:1, MINOR:2 }

// ⚠️ บั๊กที่เจอตอนรันจริงครั้งแรก (SHIP-MONITORING 2026-08-26): เดิมจับคู่ด้วย "ชื่อไฟล์" อย่างเดียว
//    (ตัดที่ ':') → ทุก finding ใน bridge.py ไปชนกับทุก cleared ใน bridge.py = conflicts ปลอม ~100 แถว
//    และ corroborated ขึ้น A+B+C หมดทุกอัน. ต้องจับที่ **ไฟล์ + บรรทัดที่ใกล้กัน** เท่านั้น
const normPath = s => String(s || '').toLowerCase().replace(/\\/g, '/').replace(/[^a-z0-9/._-]+/g, '')
const locOf = s => {
  const raw = String(s || '').trim()
  const head = raw.split(/\s+[@(—·]|\s{2,}/)[0].trim()   // ตัดคำอธิบายท้าย: "@sha", "(ทางเรียก: ...)", "— absence anchor"
  const m = head.match(/^(.*?):(\d+)/)
  if (m) return { path: normPath(m[1]), line: parseInt(m[2], 10) }
  return { path: normPath(head.split(':')[0]), line: null, label: norm(raw) }
}
const NEAR = 30   // บรรทัดห่างกันไม่เกินนี้ = ถือว่าพูดถึงจุดเดียวกัน
const sameSpot = (a, b) => {
  const x = locOf(a), y = locOf(b)
  if (!x.path || x.path !== y.path) return false
  if (x.line !== null && y.line !== null) return Math.abs(x.line - y.line) <= NEAR
  // ไม่มีเลขบรรทัด (เช่น absence anchor / ชื่อเทสต์) → ต้องเป็นข้อความเดียวกันจริงๆ ถึงนับ
  return (x.label || '') === (y.label || '')
}
const spotKey = s => { const l = locOf(s); return l.line === null ? `${l.path}#${l.label || ''}` : `${l.path}:${Math.round(l.line / NEAR)}` }

// ── ผลรวมทุกบริษัท ──
const allFindings = reports.flatMap(r => (r.findings || []).map(f => ({ ...f, firm: r.firm })))
  .sort((a,b) => (sev[a.severity] ?? 9) - (sev[b.severity] ?? 9))
const allCleared = reports.flatMap(r => (r.cleared || []).map(c => ({ ...c, firm: r.firm })))

// ── ① เทียบคะแนนรวมของแต่ละบริษัท (หัวใจของดีไซน์นี้) ──
const firmScores = reports.map(r => ({
  firm: r.firm,
  overall: r.overallScore,
  from: r.overallScoreFrom,
  findings: (r.findings || []).length,
  blockers: (r.findings || []).filter(f => f.severity === 'BLOCKER').length,
  dimsScored: (r.dimensionScores || []).length,
  confidence: r.confidence,
}))
const nums = firmScores.map(f => f.overall).filter(n => typeof n === 'number' && n > 0)
const spread = nums.length ? Math.max(...nums) - Math.min(...nums) : null
const scoreAgreement = spread === null ? 'ไม่มีคะแนน'
  : spread === 0 ? `✅ ทั้ง 3 บริษัทให้ ${nums[0]} เท่ากัน — เชื่อถือได้สูง`
  : spread === 1 ? `🟡 ต่างกัน 1 ระดับ (${nums.join('/')}) — ปกติ ดูว่ามิติไหนทำให้ต่าง`
  : `🔴 ต่างกัน ${spread} ระดับ (${nums.join('/')}) — **มีบริษัทที่ตรวจหลุด หรือเห็นอะไรที่คนอื่นไม่เห็น ต้องสืบ**`

// ── ② เทียบคะแนนรายมิติ: มิติไหนที่ 3 บริษัทเห็นไม่ตรงกัน = จุดที่ต้องเปิดโค้ดเอง ──
const byDim = {}
reports.forEach(r => (r.dimensionScores || []).forEach(d => {
  const k = String(d.dimension || '').trim().charAt(0).toUpperCase()
  if (!k) return
  ;(byDim[k] = byDim[k] || []).push({ firm: r.firm, score: d.score, why: d.why })
}))
const dimensionComparison = Object.keys(byDim).sort().map(k => {
  const rows = byDim[k]
  const ns = rows.map(x => x.score).filter(n => typeof n === 'number' && n > 0)
  const sp = ns.length > 1 ? Math.max(...ns) - Math.min(...ns) : 0
  return { dimension: k, scores: rows.map(x => `${x.firm}=${x.score}`).join(' '), spread: sp,
           flag: sp >= 2 ? '🔴 เห็นไม่ตรงกันมาก' : sp === 1 ? '🟡' : '✅', why: rows.map(x => `${x.firm}: ${x.why}`) }
})
const missingDims = reports.filter(r => (r.dimensionScores || []).length < 10)
  .map(r => `บริษัท ${r.firm} ให้คะแนนแค่ ${(r.dimensionScores||[]).length}/10 มิติ`)

// ── ③ finding: กี่บริษัทเจอ "จุดเดียวกัน" (ไฟล์ + บรรทัดใกล้กัน ไม่ใช่แค่ชื่อไฟล์) ──
const clusters = []                       // [{ members:[finding], firms:Set }]
allFindings.forEach(f => {
  const hit = clusters.find(cl => cl.members.some(m => sameSpot(m.file, f.file)))
  if (hit) { hit.members.push(f); hit.firms.add(f.firm) }
  else clusters.push({ members: [f], firms: new Set([f.firm]) })
})
const corroborated = clusters.filter(cl => cl.firms.size > 1).map(cl => {
  const worst = cl.members.slice().sort((a,b) => (sev[a.severity] ?? 9) - (sev[b.severity] ?? 9))[0]
  return { severity: worst.severity, file: worst.file, dimension: worst.dimension,
           firms: [...cl.firms].sort(),
           titles: cl.members.map(m => `${m.firm}: ${m.title}`) }
})
const solo = clusters.filter(cl => cl.firms.size === 1).flatMap(cl =>
  cl.members.map(f => ({ severity: f.severity, title: f.title, file: f.file, dimension: f.dimension, firm: f.firm })))

// ── ④ ขัดกัน: บริษัทหนึ่งยื่นเป็นบั๊ก "ตรงจุดเดียวกัน" ที่อีกบริษัทเคลียร์ทิ้ง (dedupe แล้ว) ──
const seenConflict = new Set()
const conflicts = []
allFindings.forEach(f => allCleared.forEach(c => {
  if (c.firm === f.firm) return
  if (!sameSpot(c.file, f.file)) return
  const k = `${spotKey(f.file)}|${f.firm}|${c.firm}|${norm(f.title)}`
  if (seenConflict.has(k)) return
  seenConflict.add(k)
  conflicts.push({ file: f.file, filedBy: f.firm, severity: f.severity, finding: f.title,
                   clearedBy: c.firm, clearedAt: c.file, clearedWhat: c.what, clearedReason: c.whyNotAProblem })
}))

// ── ⑤ เจตนา/ขอบเขต ตรงกันไหม ──
const intents = reports.map(r => ({ firm: r.firm, target: r.sheet?.header?.target || '(ไม่ระบุ)',
                                    intent: r.sheet?.header?.intent || '(ไม่ระบุ)', tag: r.sheet?.header?.intentTag || '?' }))
const intentAgreement = new Set(intents.map(i => norm(i.intent))).size === 1
  ? '✅ ทั้ง 3 บริษัทเข้าใจเจตนาตรงกัน'
  : '⚠️ เข้าใจเจตนาไม่ตรงกัน — Coddy ต้องตัดสินว่าเจตนาจริงคืออะไรก่อนชั่งน้ำหนัก findings'

// ── ⑥ ความครบถ้วนของงานแต่ละบริษัท (จับบริษัทที่ทำลวกๆ) ──
const thoroughness = reports.map(r => {
  const s = r.sheet || {}
  const gaps = []
  if (!(s.trace || []).length) gaps.push('ไม่มี [TRACE] — ไม่ได้เดินเส้นทาง')
  if (!(s.map?.entryPoints || []).length) gaps.push('ไม่มีจุดเข้า')
  if (!(s.map?.callers || []).length) gaps.push('ไม่ได้หาคนเรียก')
  if (!(s.map?.siblings || []).length) gaps.push('ไม่ได้หาพี่น้อง')
  if (!s.map?.instances) gaps.push('ไม่ได้ระบุว่าอ่านสำเนาไหน')
  if (!(s.questionsResolved || []).length && (s.questions || []).length) gaps.push('เปิด [Q] แล้วไม่ปิด')
  if ((r.dimensionScores || []).length < 10) gaps.push(`ให้คะแนนแค่ ${(r.dimensionScores||[]).length}/10 มิติ`)
  if (!r.notCovered) gaps.push('ไม่บอกว่าอะไรไม่ได้ตรวจ')
  return { firm: r.firm, traceHops: (s.trace || []).length, dims: (r.dimensionScores || []).length,
           findings: (r.findings || []).length, cleared: (r.cleared || []).length,
           gaps: gaps.length ? gaps : ['ครบทุกพาท'] }
})

log(`reviver เสร็จ: ${reports.length}/3 บริษัท · คะแนน ${firmScores.map(f=>f.firm+'='+f.overall).join(' ')} · ${scoreAgreement.replace(/[✅🟡🔴]/g,'').trim()} · findings ${allFindings.length} (ตรงกัน ${corroborated.length} · เดี่ยว ${solo.length}) · ขัดกัน ${conflicts.length}`)

return {
  agentsUsed: FIRMS.length,          // = 3 เสมอ (script บังคับ)
  design: '3 บริษัทอิสระ ทำงานเดียวกันครบ 7 พาท × 10 มิติ — ไม่ได้แบ่งงานกันทำ',
  target: target || '(การเปลี่ยนแปลงปัจจุบัน — ดู intents ว่าแต่ละบริษัทเลือกอะไร)',

  scoreAgreement,
  firmScores,
  dimensionComparison,
  missingDims,
  intentAgreement,
  intents,
  thoroughness,

  corroborated,
  solo,
  conflicts,
  findings: allFindings,
  cleared: allCleared,
  fullReports: reports,

  next: [
    'Coddy (ตัวหลัก) ทำต่อ 0 agent — นี่คือขั้น "ประเมินผลของแต่ละบริษัท":',
    '1) ดู `scoreAgreement` ก่อน — ต่างกัน ≥2 ระดับ = มีบริษัทตรวจหลุดหรือเห็นอะไรที่คนอื่นไม่เห็น **ต้องสืบว่าใครถูก**',
    '2) ดู `thoroughness` — บริษัทที่มี gaps (ไม่มี TRACE / ไม่หาพี่น้อง / ให้คะแนนไม่ครบ 10 มิติ) = ผลของบริษัทนั้นน้ำหนักน้อยลง **ต้องบอกใน รายงาน**',
    '3) `dimensionComparison` — มิติที่ 🔴 คือจุดที่ต้อง**เปิดโค้ดจริงตัดสินเอง**',
    '4) `conflicts` — บริษัทหนึ่งยื่นเป็นบั๊ก อีกบริษัทเคลียร์ทิ้ง → **เปิดโค้ดจริง ห้ามเชื่อฝั่งใดฝั่งหนึ่ง**',
    '5) `corroborated` (หลายบริษัทเจอตรงกัน) = มั่นใจสูง · `solo` = verify กับโค้ดจริงก่อนรายงาน',
    '6) คะแนนสุดท้ายที่รายงาน Nick = **มิติต่ำสุดจากภาพรวมที่ verify แล้ว** ไม่ใช่ค่าเฉลี่ยของ 3 บริษัท',
    '7) รายงานต้องมี: findings + **cleared (ตรวจแล้วไม่ต้องแก้)** + **notCovered (ไม่ได้ตรวจ)** + คะแนนของแต่ละบริษัทและเหตุผลที่ต่างกัน',
    '8) ❌ **ไม่แก้โค้ดอัตโนมัติ** — เสนอแผนแก้ + blast radius แล้วถาม Nick ก่อน เว้นแต่สั่งมาแล้ว',
  ].join('\n'),
}
