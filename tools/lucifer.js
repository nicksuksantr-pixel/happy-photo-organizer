export const meta = {
  name: 'lucifer',
  description: 'Lucifer — ทีม 3 ตัวรีเลย์ (① วางแผน → ② โค้ด → ③ Scrutinize รีวิวให้คะแนน 1–5) + ด่านคะแนน วนสูงสุด 2 รอบ',
  phases: [
    { title: 'วิเคราะห์', detail: '① สถาปนิก อ่านโค้ดปัจจุบัน → ออกแผน' },
    { title: 'เขียนโค้ด', detail: '② เขียนโค้ดตามแผน (ใน worktree ที่ Coddy เตรียม)' },
    { title: 'รีวิว',     detail: '③ Lucifer panel 3 ตัว (วิธี Scrutinize) ให้คะแนน 1–5 เอาต่ำสุด' },
  ],
}

// ───────────────────────────────────────────────────────────────────────
// เรียกผ่าน: Nick พิมพ์ "Lucifer: <งาน>" → Coddy ทำตาม command_pattern ข้อ 12:
//   1) Coddy สร้าง git worktree แยกจาก main → ส่ง path เข้าทาง args.workdir (ของจริงไม่ถูกแตะ)
//   2) เรียก Workflow tool: { scriptPath: "<ไฟล์นี้>", args: { task, workdir } }
//   3) ผลกลับมา:
//        passed=true  → Coddy: emulator test → build → อัพ Play internal (❌ ไม่ต้องอัพ Drive) → merge worktree
//        passed=false → Coddy: ❌ ไม่ build/ไม่อัพ → ทิ้ง worktree → คุยกับนิก
// ❌ ห้ามจำลอง 3 agent เอง / ห้ามให้คะแนนตัวเอง / ห้าม build ก่อนผ่าน — ตัว script บังคับให้เป๊ะ
// ───────────────────────────────────────────────────────────────────────

// ⚠ args มาถึงสคริปต์เป็น JSON "string" ในฮาร์เนสนี้ (พิสูจน์ 2026-06-13: ส่ง object → typeof args==='string')
// → ต้อง parse ก่อนเสมอ + กัน throw (JSON.parse("undefined")/quote แตก = SyntaxError) · ❌ ห้ามลบ guard นี้
let _A = args
if (typeof _A === 'string') { try { _A = JSON.parse(_A) } catch { _A = {} } }
_A = _A || {}
const task = _A.task, workdir = _A.workdir
if (!task || !workdir)
  return { passed:false, error:'lucifer: ไม่มี task/workdir ใน args — ส่ง args เป็น object {task,workdir} (Workflow แปลงเป็น string สคริปต์ parse เอง)', rawType: typeof args }

const PLAN = { type:'object', required:['summary','changes','acceptance'], properties:{
  summary:{type:'string'}, acceptance:{type:'array', items:{type:'string'}},
  changes:{type:'array', items:{type:'object', required:['file','what','why'],
    properties:{file:{type:'string'}, what:{type:'string'}, why:{type:'string'}}}} }}
const CODE = { type:'object', required:['filesChanged','summary'], properties:{
  filesChanged:{type:'array', items:{type:'string'}}, summary:{type:'string'}, deviations:{type:'string'} }}
const REVIEW = { type:'object', required:['score','verdict','issues'], properties:{
  score:{type:'integer', minimum:1, maximum:5}, verdict:{type:'string'},
  issues:{type:'array', items:{type:'object', required:['severity','file','problem','fix'],
    properties:{severity:{type:'string'}, file:{type:'string'}, problem:{type:'string'}, fix:{type:'string'}}}} }}

const LENS = [
  'ตรงโจทย์ที่นิกสั่งจริงไหม + ความถูกต้องของ logic',
  'คุณภาพ / ความสวยงาม / UX + ความสะอาดของโค้ด',
  'ความเสี่ยง: regression, edge case, ของเดิมพังไหม',
]

const planPrompt = (round, fb) => [
  `คุณคือ ① สถาปนิก/นักวิเคราะห์ ของทีม Lucifer`,
  `โจทย์จากนิก: "${task}"`,
  `อ่าน "โค้ดปัจจุบันล่าสุด" ใน ${workdir} เท่านั้น — ❌ ห้ามอ่านโค้ดเก่า/เวอร์ชันก่อน/โปรเจคอื่น (เปลืองโทเค้น)`,
  round > 1 ? `รอบ ${round} — รอบก่อนยังไม่ผ่าน แก้ตามรีวิวนี้:\n${fb}` : ``,
  `ออก "แผน" ที่ชัดที่สุดเพื่อแก้โจทย์ให้ดีที่สุดตามที่นิกต้องการ: แก้ไฟล์ไหน/ทำอะไร/ทำไม + acceptance ("ดี" คือแบบไหน)`,
  `❌ อย่าเพิ่งเขียนโค้ด — แค่วางแผน`,
].filter(Boolean).join('\n')

const codePrompt = (plan) => [
  `คุณคือ ② ช่างเขียนโค้ด ของทีม Lucifer · ทำตามแผนของ ① เป๊ะ:`,
  JSON.stringify(plan, null, 2),
  `โจทย์: "${task}"`,
  `เขียน/แก้โค้ดจริง "เฉพาะใน ${workdir}" (worktree แยก — ของจริงปลอดภัย) · ครบ ใช้ได้จริง · เบี่ยงจากแผนให้บอกใน deviations`,
].join('\n')

// ③ ใช้วิธี "Scrutinize" (skill: ~/.claude/skills/scrutinize/SKILL.md) — รีวิวแบบคนนอก end-to-end
const reviewPrompt = (plan, code, lens) => [
  `คุณคือ ③ "Lucifer" — นักรีวิวตัวแทนนิก เข้มงวดสุด · ใช้วิธี **Scrutinize** (รีวิวแบบคนนอก end-to-end)`,
  `จุดยืน: ลืมว่าใครเขียน/ทำไม อ่าน cold · ❌ ห้าม rubber-stamp ("LGTM" ใช้ไม่ได้) · ❌ ห้ามประจบ · cite file:line เสมอ · แยก "claim (โค้ดบอกว่า)" กับ "ตรวจแล้วยืนยัน/ค้าน"`,
  `โจทย์ที่นิกสั่ง: "${task}"`,
  `แผนของ ①: ${JSON.stringify(plan)}`,
  ``,
  `📌 **เริ่มจากหลักฐานก่อน แล้วค่อยอ่านคำบอกเล่า** (audit ตัวเอง 2026-08-27 · บทเรียน "คอมเมนต์ไม่ใช่หลักฐาน"):`,
  `  1) รัน \`git -C ${workdir} diff\` (และ \`git -C ${workdir} status\`) **ดูของจริงที่เปลี่ยนด้วยตาตัวเองก่อน**`,
  `  2) ค่อยอ่านรายงานตัวเองของ ② ข้างล่างนี้ — มันคือ **คำกล่าวอ้าง** ไม่ใช่หลักฐาน`,
  `  3) ถ้า \`filesChanged\` ที่ ② บอก **ไม่ตรงกับ diff จริง** (แจ้งไม่ครบ / แจ้งเกิน / แตะไฟล์ที่ไม่ได้อยู่ในแผน)`,
  `     → นั่นคือ issue ที่ต้องยื่น ไม่ใช่รายละเอียดปลีกย่อย: รีวิวที่ยึดสรุปของคนเขียนคือรีวิวที่ถูกนำทาง`,
  `รายงานตัวเองของ ② (คำกล่าวอ้าง): ${JSON.stringify(code)}`,
  `ทำ 4 step ตามลำดับ (ห้ามข้าม):`,
  `  1) INTENT — พูดเป้าหมายเป็นประโยคเดียว · **บังคับถาม: มีวิธีง่าย/เล็ก/สวยกว่าที่ได้ผลเท่ากันไหม** (ทำเฉยๆ? ใช้ของที่มีอยู่แล้ว? แก้คนละ layer? เล็กกว่าแก้ 90% เสี่ยง 10%) — ถ้ามี เสนอก่อนเลย`,
  `  2) TRACE — เดิน code path จริง end-to-end (entry→call→branch→state→exit) รวมโค้ดที่ไม่ได้แก้รอบๆ diff ด้วย (bug ซ่อนที่รอยต่อ) ไม่ใช่ดูแค่ diff`,
  `  3) VERIFY — claim แต่ละอันจริงไหม (เดิน path ให้เห็น) · input/state อะไรพัง (edge/concurrent/error/null/empty/ใหญ่/ลำดับ) · อะไรเปลี่ยนเงียบๆ (perf/error-semantics/contract/format) · test ครอบ path จริง หรือ happy-path/mock บัง`,
  `  4) เน้นมุมพิเศษของคุณ: ${lens}`,
  `สรุป → verdict (ship / fix-then-ship / rework / reject) + score 1–5 ให้ตรงกับ verdict:`,
  `  5=ship (ตรงเป๊ะ trace ผ่านหมด) · 4=fix-then-ship เหลือจุดเล็ก · 3=มีจุดต้องแก้ชัด · 2=rework หลายจุด/structural · 1=reject ผิดทาง`,
  `ใส่ verdict ลง field "verdict" · issues ทุกจุด (severity/file/problem/fix · เรียง blocker→nit · อย่า pad nit ถ้ามีปัญหา structural) · ไม่แน่ใจ=ให้ต่ำไว้ก่อน`,
].join('\n')

const MAX_ROUNDS = 2
let review, plan, code, feedback = ''

for (let round = 1; round <= MAX_ROUNDS; round++) {
  // ① วางแผน — relay: await บังคับให้ "จบก่อน" ② เริ่ม
  plan = await agent(planPrompt(round, feedback), { label:`①วางแผน·รอบ${round}`, phase:'วิเคราะห์', schema: PLAN })

  // ② เขียนโค้ด — เริ่ม "หลัง" ① เท่านั้น (ขนานไม่ได้)
  code = await agent(codePrompt(plan), { label:`②เขียนโค้ด·รอบ${round}`, phase:'เขียนโค้ด', schema: CODE })

  // ③ Lucifer panel 3 ตัว — agent คนละตัวกับ ② → "ให้คะแนนตัวเองไม่ได้"
  const panelRaw = await parallel(LENS.map((lens, i) => () =>
    agent(reviewPrompt(plan, code, lens), { label:`③Lucifer#${i+1}·รอบ${round}`, phase:'รีวิว', schema: REVIEW })))
  // ผูกเลขผู้ตรวจกับ LENS ตามลำดับที่สคริปต์รู้ (parallel รักษาลำดับ) — จะได้บอกได้ว่า "มุมไหนหายไป"
  const panelSlots = LENS.map((lens, i) => ({ no: i + 1, lens, result: panelRaw[i] || null }))
  const scored = panelSlots.filter(s => s.result)

  // ⛔ "ผู้ตรวจตายทั้ง panel" ≠ "งานนี้ได้ 1 คะแนน" (audit ตัวเอง 2026-08-27)
  // เดิม fallback เป็น {score:1} แล้วปล่อยไหลลงไปรอบ 2 = เปิด agent อีก 5 ตัวเต็มรอบเพราะ infra ล่ม
  // ซึ่งคือ blind-retry ที่ #16 ห้ามไว้ (เหตุ 60-agent burn) แค่ย้ายเข้ามาซ่อนอยู่ในสคริปต์
  // แถม `passed:false` ที่ได้ออกไปจะอ่านเหมือนคำตัดสินคุณภาพ ทั้งที่ไม่มีใครตรวจเลยสักคน
  if (!scored.length)
    return { passed:false, stopped:true, round, score:null, plan, code, workdir,
             error:`③ ผู้ตรวจไม่คืนผลเลยสักตัวในรอบ ${round} — นี่คือ agent ล่ม ไม่ใช่คำตัดสินคุณภาพ`,
             next:`Coddy: 🛑 STOP (#16) — ❌ ห้าม build/อัพ · ❌ **ห้ามรันรอบต่อไปเอง** (1 trigger = 1 launch) · ` +
                  `วินิจฉัยด้วย 0 agent ก่อน (ดู journal/log) → รายงาน Nick ว่า panel ล่ม แล้วรอให้เขาพิมพ์ trigger ใหม่ · ` +
                  `worktree ยังอยู่ที่ ${workdir} งานของ ② ไม่หาย` }

  const deadReviewers = panelSlots.filter(s => !s.result).map(s => `#${s.no} (${s.lens.slice(0, 28)}…)`)

  // ⛔ panel ไม่ครบ = ไม่มีสิทธิ์ปล่อยผ่าน (reviver #26 บริษัท A ยื่นเป็น BLOCKER · 2026-08-27)
  // รอบก่อนผมดักแค่ `!scored.length` = ตายครบ 3 คนเท่านั้น · พอตายไป 1-2 คน `low` คิดจากคนที่รอด
  // คนเดียวให้ 5 → passed:true → 'build → อัพ Play → merge' **ด่านคุณภาพทั้งด่านเหลือผู้ตรวจคนเดียว**
  // แย่กว่านั้น: object ที่ส่งออกมี deadReviewers อยู่ด้วย = บันทึกว่าพังแล้วไม่เอามาตัดสิน
  // ซึ่งคือรูปแบบ "ตัวเลขเปิดโล่ง วางธงซื่อสัตย์ไว้ข้างๆ" ที่การแก้ทั้งชุดนี้ตั้งใจจะลบทิ้งพอดี
  // เกณฑ์ "เอาคะแนนต่ำสุดจาก 3 มุม" จะมีความหมายก็ต่อเมื่อมีครบ 3 มุม — ขาดมุมไหนไป
  // คะแนนต่ำสุดที่ได้ก็ไม่ใช่คะแนนต่ำสุดจริง แค่ต่ำสุดของมุมที่บังเอิญรอด
  if (scored.length < LENS.length)
    return { passed:false, stopped:true, round, score:null,
             reviewersExpected: LENS.length, reviewersUsed: scored.length, deadReviewers,
             panelScores: scored.map(s => s.result.score), plan, code, workdir,
             error:`③ ผู้ตรวจคืนผลแค่ ${scored.length}/${LENS.length} ในรอบ ${round} (ขาด ${deadReviewers.join(', ')}) — ` +
                   `agent ล่ม ไม่ใช่คำตัดสินคุณภาพ`,
             next:`Coddy: 🛑 STOP (#16) — ❌ ห้าม build/อัพ Play/merge worktree เด็ดขาด: ด่านคะแนนต้องมีครบ ${LENS.length} มุม ` +
                  `คะแนนจากมุมที่รอดไม่ใช่ "คะแนนต่ำสุด" · ❌ ห้ามรันรอบต่อไปเอง (1 trigger = 1 launch) · ` +
                  `วินิจฉัย 0 agent ก่อน (journal/log) → รายงาน Nick แล้วรอให้เขาพิมพ์ trigger ใหม่ · ` +
                  `worktree ยังอยู่ที่ ${workdir} งานของ ② ไม่หาย` }

  const low = scored.reduce((m, s) => (s.result.score < m.result.score ? s : m), scored[0])
  review = low.result
  log(`รอบ ${round}: คะแนนต่ำสุด ${review.score}/5 (panel: ${scored.map(s => s.result.score).join('/')}` +
      `${deadReviewers.length ? ` ⚠ ตายไป ${deadReviewers.join(',')}` : ''})`)

  const passBar = round === 1 ? 5 : 4   // รอบ1 ต้อง 5 · รอบ2 รับ 4–5
  if (review.score >= passBar)
    return { passed:true, round, score:review.score, panelScores: scored.map(s => s.result.score),
             reviewersExpected: LENS.length, reviewersUsed: scored.length, deadReviewers,
             plan, code, review, workdir, next:'Coddy: emulator test → build → อัพ → merge worktree' }

  // ⛔ ส่งต่อ issues ของ "ผู้ตรวจทุกคน" ไม่ใช่แค่คนที่ให้คะแนนต่ำสุด (audit ตัวเอง 2026-08-27)
  // เดิม feedback = review.issues = ของผู้ตรวจคนเดียว → issues ของอีก 2 คนถูกทิ้งทั้งชุด
  // ผลจริง: รอบ 2 (ซึ่งเป็นรอบสุดท้าย) สถาปนิกแก้ตามคนเดียว แล้วผู้ตรวจอีก 2 คนก็ยื่นเรื่องที่
  // ไม่เคยถูกส่งต่อซ้ำอย่างชอบธรรม → คะแนนตก → 🛑 ไม่ build ทั้งที่แก้ได้ตั้งแต่รอบแรกถ้ารู้
  // กฎ "เอาคะแนนต่ำสุด" มีไว้ตัดสิน "ผ่าน/ไม่ผ่าน" — ไม่ได้มีไว้เลือกว่าจะฟัง feedback ของใคร
  const seen = new Set()
  const allIssues = scored
    .flatMap(s => (s.result.issues || []).map(x => ({ ...x, by: `ผู้ตรวจ#${s.no}` })))
    .filter(x => {
      // ⚠ คีย์ต้องเป็น "ข้อความเต็ม" ไม่ใช่ 80 ตัวอักษรแรก (reviver #26 บริษัท A · 2026-08-27):
      // ฉบับแรกตัดที่ 80 ตัว → ปัญหาคนละเรื่องที่ขึ้นต้นเหมือนกัน (ซึ่งเป็นวิธีเขียนปกติของภาษาไทย
      // "ในไฟล์ X ฟังก์ชัน Y ...") จะถูกนับเป็นอันเดียวกันแล้วโดนทิ้ง = สร้างการสูญหายแบบแคบลง
      // ซ้ำรอยบั๊กที่การแก้นี้เพิ่งลบไปเอง · **ยอมซ้ำดีกว่ายอมหาย** — สถาปนิกอ่านของซ้ำได้ แต่หาของที่ไม่เคยเห็นไม่ได้
      const k = `${String(x.file).toLowerCase().trim()}|${String(x.problem).toLowerCase().replace(/\s+/g, ' ').trim()}`
      if (seen.has(k)) return false
      seen.add(k); return true
    })
  feedback = allIssues.map(x => `- [${x.severity}] (${x.by}) ${x.file}: ${x.problem} → ${x.fix}`).join('\n')
}

// รอบ 2 ยังได้ 1–3 → ไม่ผ่าน (❌ ไม่มีรอบ 3)
return { passed:false, round:MAX_ROUNDS, score:review.score, plan, code, review, workdir, next:'Coddy: ❌ ไม่ build/ไม่อัพ → ทิ้ง worktree → วิเคราะห์ + คุยกับนิก' }
