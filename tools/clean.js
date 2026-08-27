export const meta = {
  name: 'clean',
  description: 'clean — 3 "บริษัท" อิสระ วิเคราะห์ "ชั้นเดียว" ของโปรเจคครบทั้ง 3 มุม (โครงสร้าง · ความสะอาด · รูปแบบ+ความเร็ว) ด้วยตัวเองทุกบริษัท แล้วเอาผลมาเทียบกัน · ไม่ได้แบ่งงานกันทำ · agent อ่านอย่างเดียว ห้ามแก้ไฟล์ · **ทริกเกอร์นี้จบที่รายงาน** การลงมือแก้เป็นคำสั่งแยกที่ Nick สั่งเอง',
  phases: [
    { title: 'วิเคราะห์', detail: '3 บริษัทอิสระ · แต่ละบริษัทดูครบทั้ง 3 มุมด้วยตัวเอง → ข้อเสนอ + วิธีพิสูจน์ว่าพฤติกรรมไม่เปลี่ยน' },
  ],
}

// ───────────────────────────────────────────────────────────────────────
// command_pattern #27 "clean" (Nick 2026-08-27)
//
// แกนของทริกเกอร์นี้ประโยคเดียว:
//   clean = เปลี่ยน "รูป" ไม่เปลี่ยน "พฤติกรรม"
//   ถ้าพิสูจน์ไม่ได้ว่าข้างนอกไม่ขยับ มันไม่ใช่การรีแฟกเตอร์ — มันคือการเขียนใหม่ที่มาในชื่อสวยๆ
//
// ทำไมต้อง "3 บริษัททำงานเดียวกัน" ไม่ใช่ "3 agent แบ่งมุมกันดู" (Nick แก้ดีไซน์แรกของ Coddy):
//   บั๊กมีจริงหรือไม่มีจริง วัดได้ — แต่ "โค้ดนี้อ่านง่ายกว่า" เป็น "รสนิยม"
//   ข้อเสนอรีแฟกเตอร์จึงต้องการการยืนยันข้ามผู้ตรวจมากกว่าการล่าบั๊กเสียอีก
//   การแบ่งมุมกันดู = การกระจายงาน ไม่ใช่การตรวจทาน (บทเรียนเดียวกับ reviver #26)
//
// ⛔ ทริกเกอร์นี้ไม่แก้โค้ด: agent อ่านอย่างเดียว และ "ตัวสคริปต์จบที่รายงาน"
//    Coddy ห้ามไหลไปแก้ต่อเอง — Nick อ่านรายงานแล้วสั่งเป็นคำสั่งใหม่ว่าจะเอาข้อไหน
//    เหตุผล: clean ไปแตะโค้ดที่ "ทำงานอยู่ดีๆ" ซึ่งเสี่ยงกว่าทุกทริกเกอร์ในบ้าน
//    (ต่างจาก Tester #5 ที่แก้เองได้ เพราะมันไล่ตามของที่พังอยู่แล้ว)
//
// ⛔ AGENT CAP #16: parallel ครั้งเดียว เป๊ะ 3 · ไม่มี fan-out ตามข้อเสนอ · agent ห้าม spawn ต่อ
// ───────────────────────────────────────────────────────────────────────

// args มาถึงเป็น JSON "string" ในฮาร์เนสนี้ (พิสูจน์ 2026-06-13) → parse + กัน throw · ห้ามลบ guard
let _A = args
if (typeof _A === 'string') { try { _A = JSON.parse(_A) } catch { _A = {} } }
_A = _A || {}

const workdir  = (_A.workdir  || '').toString().trim()
const layer    = (_A.layer    || '').toString().trim()
const backup   = (_A.backup   || '').toString().trim()
const branch   = (_A.branch   || '').toString().trim()
const baseline = (_A.baseline || '').toString().trim()

// 🧹 housekeeping (#6/#7) — Nick, 2026-08-28: *"tidy ใส่ไปใน clean เลยไม่ได้หรอ จะได้จัดการทั้งโค้ดและโฟลเดอร์ไปด้วยเลย"*
// ใส่ "ตรรกะ" ของ tidy ลงในสคริปต์นี้ไม่ได้ — สคริปต์ Workflow ไม่มี fs/Node API มันสั่งได้แค่ agent
// แต่ทำให้เป็น "ขั้นตอนหนึ่งของทริกเกอร์" ได้: Coddy รัน `node tidy.mjs --project <proj>` ตอนเตรียมงาน
// (0 agent · ~1 วินาที · 0 โทเค้น) แล้วส่งผลมาทางช่องนี้ → รายงานโค้ดกับรายงานโฟลเดอร์ออกมาก้อนเดียว
//
// ⚠ **ไม่ใช่ประตู** (ต่างจาก 4 ตัวข้างล่าง) — housekeeping ที่พังต้องไม่บล็อกการรีวิวโค้ด
//    แต่ก็ไม่ปล่อยเงียบ: ไม่ได้รัน = ขึ้นธงในรายงาน ไม่ใช่หายไปเฉยๆ
// ❌ และ agent ไม่ยุ่งกับเรื่องนี้เลยแม้แต่นิดเดียว — "ไฟล์นี้อยู่ในถัง 92 วัน" คือเลขคณิต ไม่ใช่วิจารณญาณ (#26.1)
const housekeeping = (_A.housekeeping || '').toString().trim()

const bad = m => ({ error: 'clean: ' + m + ' · ไม่เปิด agent ใดๆ', proposals: [], firms: [] })

if (!workdir) return bad('ไม่มี workdir ใน args — ส่ง { workdir, layer, backup, branch, baseline }')

// ⛔ ประตูความปลอดภัยอยู่ "ในโค้ด" ไม่ใช่ในเอกสาร (บทเรียน 2026-08-27: การ์ดที่ไม่มีใครเรียก = คอมเมนต์)
// สคริปต์ปฏิเสธที่จะเปิด agent จนกว่า Coddy จะทำ 4 อย่างนี้จริงและส่งหลักฐานมา
if (!layer)
  return bad('ไม่มี `layer` — clean ทำ "ทีละชั้น" เท่านั้น ไม่ใช่ทั้ง repo. ' +
             'ชั้น = ส่วนที่บอกได้ว่า "ขอบข้างนอกคืออะไร" (เช่น ชั้นข้อมูล = store.py + schema ตาราง). ' +
             'บอกขอบไม่ได้ = ยังไม่ใช่ชั้น = พิสูจน์ "พฤติกรรมไม่เปลี่ยน" ไม่ได้ เพราะไม่รู้จะวัดอะไร')
if (!backup)
  return bad('ไม่มี `backup` — Nick สั่งว่าต้องแบ็คอัพก่อนรัน clean ทุกครั้ง. ' +
             'ทำ zip ลง Backups/<project>_pre-clean_v<ver>_<วันเวลา>.zip แล้วส่ง path มา')
if (!branch)
  return bad('ไม่มี `branch` — clean ทำงานบน branch แยก (clean/v<ver>) ของจริงบน main ห้ามถูกแตะ')
if (!baseline)
  return bad('ไม่มี `baseline` — ต้องรันชุดเทสต์ "ก่อน" แตะอะไรทั้งสิ้น แล้วส่งผลมา. ' +
             'เทสต์แดงอยู่แล้ว = ไม่มี baseline = พิสูจน์ไม่ได้ว่าเราไม่ได้ทำพัง → หยุด อย่าเริ่ม')

const ASPECTS = [
  '① โครงสร้าง (refactoring) — โค้ดซ้ำ/สำเนาที่จะ drift · ฟังก์ชันยักษ์ที่ทำหลายอย่าง · ของชิ้นเดียวมีเจ้าของหลายคน · อยู่ผิดชั้น (UI รู้เรื่อง SQL, ตรรกะรู้เรื่องหน้าจอ) · โค้ดตาย · ทางอ้อมที่ไม่มีใครใช้',
  '② ความสะอาด (clean code) — ชื่อที่ไม่บอกว่ามันคืออะไร · ความซับซ้อนเกินจำเป็น (เงื่อนไขซ้อนลึก, flag ที่ทำให้ฟังก์ชันมี 2 บุคลิก) · เลขลอยไม่มีชื่อ · **คอมเมนต์ที่บรรยายโค้ดที่เดินหน้าไปแล้ว**',
  '③ รูปแบบ + ความเร็ว — indentation/วางปีกกา/ความสม่ำเสมอ (มี formatter ใช้ไหม ตั้งค่าไว้หรือยัง) · และ hot path ที่ **วัดได้จริง** เท่านั้น',
]

const STR = { type: 'string' }
const S = n => ({ type: 'string', maxLength: n })
// required บาง ๆ โดยตั้งใจ: 21 ช่องเคยทำให้ 2 ใน 3 บริษัทตายด้วย StructuredOutput retry cap (2026-08-27)
// ช่องอื่นยังขอครบใน prompt แต่ไม่ hard-fail — ปล่อยให้ `thoroughness` เป็นคนจับคนที่ทำลวกแทน
//
// ⛔ และ **ความยาว** คือสาเหตุที่แท้จริงของการตายนั้น ไม่ใช่จำนวนช่อง (transcript จริง 2026-08-27):
// ข้อความที่ harness ตอบกลับมาคือ "could not be parsed as JSON" — บริษัทที่ตายส่ง 36-68 KB ทุกครั้ง
// = ยาวเกินโควตา output → ถูกตัดกลางประโยค → วงเล็บปิดไม่ครบ → ลองใหม่ก็ยาวอีก → ครบ 5 ครั้งตาย
// `maxLength` ทำให้ "ยาวเกิน" กลายเป็น error แบบไม่ตรงสคีมา ซึ่งโมเดลอ่านรู้เรื่องและแก้ได้เอง
// ❌ ห้ามถอดออก · เพิ่มช่องใหม่ต้องผูกความยาวมาด้วยเสมอ
const REPORT = {
  type: 'object',
  required: ['firm', 'verdictSummary', 'layerBoundary', 'proposals', 'notCovered', 'confidence'],
  properties: {
    firm: STR,
    verdictSummary: S(1200),
    layerBoundary: S(2500),      // "ข้างนอก" ของชั้นนี้คืออะไร = สิ่งที่ห้ามขยับ (ยาวได้ — เป็นสัญญาที่ต้องครบ)
    entryPoints: { type: 'array', items: S(240), maxItems: 20 },
    readOrder: { type: 'array', items: S(240), maxItems: 20 },
    testCoverage: S(900),        // ส่วนไหนของชั้นนี้มีเทสต์คุ้ม ส่วนไหนไม่มี
    formatter: S(600),           // โปรเจคนี้มี formatter ไหม ตั้งค่าไว้ยัง ควรใช้ตัวไหน
    proposals: {
      type: 'array',
      // ⚠ maxItems ที่นี่ตัด "ของจริง" ไม่ใช่แค่ตัดข้อความ → prompt สั่งไว้ว่าเกินแล้วต้องนับที่เหลือ
      // ลง notCovered ห้ามหายเงียบ (การตัดขอบเขตแบบไม่ประกาศ = ข้อบกพร่องของตัวรีวิวเอง — รูบริค)
      maxItems: 15,
      items: {
        type: 'object',
        required: ['aspect', 'title', 'file', 'problem', 'proposal', 'behaviourProof'],
        properties: {
          aspect: { type: 'string', enum: ['structure', 'clarity', 'format-perf'] },
          title: S(140),
          file: S(200),          // file:line เสมอ
          problem: S(600),       // "ทำไมรูปทรงปัจจุบันเป็นปัญหา" ไม่ใช่ "มันไม่สวย"
          proposal: S(700),      // จะเปลี่ยนเป็นอะไร
          behaviourProof: S(700),// ⭐ ช่องที่นิยามทริกเกอร์นี้ — จะพิสูจน์ยังไงว่าข้างนอกไม่ขยับ
          blastRadius: S(350),
          effort: S(160),
          coveredByTests: S(200),// yes / partial / no — "no" ต้องเขียน characterization test ก่อน
          measured: S(400),      // เฉพาะข้อเสนอความเร็ว: ตัวเลขก่อน/หลัง ไม่มีตัวเลข = ไม่ใช่ข้อเสนอความเร็ว
        },
      },
    },
    notCovered: S(1500),
    confidence: S(900),
  },
}

const buildPrompt = (firm) => [
  `คุณคือ **บริษัท "${firm}"** — หนึ่งใน 3 บริษัทที่ Nick จ้างมาพร้อมกันสำหรับงาน \`clean\``,
  ``,
  `**สำคัญที่สุด — เข้าใจบทบาทให้ถูก:** ทั้ง 3 บริษัทได้โจทย์ **เดียวกันเป๊ะ** และต้องดู **ครบทั้ง 3 มุม** ด้วยตัวเอง`,
  `❌ ไม่ได้แบ่งมุมกันดู — การแบ่งงานคือการกระจายงาน ไม่ใช่การตรวจทาน`,
  `Coddy จะเอาข้อเสนอของ 3 บริษัทมาเทียบกัน: **ข้อที่หลายบริษัทเห็นตรงกัน = ของจริง · ข้อที่เจอคนเดียว = อาจเป็นแค่รสนิยม**`,
  ``,
  `═══ แกนของงานนี้ ═══`,
  `**clean = เปลี่ยนรูป ไม่เปลี่ยนพฤติกรรม** ถ้าพิสูจน์ไม่ได้ว่าข้างนอกไม่ขยับ นั่นไม่ใช่รีแฟกเตอร์ แต่คือการเขียนใหม่`,
  `ทุกข้อเสนอต้องกรอกช่อง \`behaviourProof\` ให้ได้ — **ตอบช่องนี้ไม่ได้ = ไม่ใช่ข้อเสนอของ clean ตัดทิ้ง ไม่ต้องยื่น**`,
  ``,
  `═══ ขอบเขต ═══`,
  `โปรเจค: ${workdir}`,
  `**ชั้นที่ต้องดู (ชั้นเดียวเท่านั้น): ${layer}**`,
  `งานแรกของคุณคือเขียน \`layerBoundary\` ออกมา = **"ข้างนอก" ของชั้นนี้คืออะไร** (ฟังก์ชัน/คลาสสาธารณะ + signature · route · argument · schema · สัญญา JSON ที่ฝั่งอื่นใช้)`,
  `สิ่งที่อยู่ใน layerBoundary คือ **สิ่งที่ห้ามขยับ** — ทุกข้อเสนอต้องไม่แตะมัน`,
  `❌ อย่าไล่อ่านนอกชั้นนี้ (เห็นปัญหาร้ายแรงนอกชั้นยื่นได้ แต่บอกให้ชัดว่าอยู่นอกขอบเขต)`,
  ``,
  `═══ สถานะที่ Coddy เตรียมไว้แล้ว (ไม่ต้องทำซ้ำ) ═══`,
  `แบ็คอัพ: ${backup}`,
  `branch: ${branch}`,
  `**baseline เทสต์ก่อนแตะอะไร: ${baseline}**  ← นี่คือหลักฐานว่าของเดิมทำงานอยู่ ข้อเสนอทุกข้อต้องรักษาสถานะนี้ไว้`,
  ``,
  `═══ 3 มุมที่ต้องดูให้ครบทุกมุม ═══`,
  ...ASPECTS.map(a => `  ${a}`),
  ``,
  `═══ กฎที่ห้ามยืดหยุ่น ═══`,
  `  1. **เจอบั๊กระหว่างทาง → ห้ามเสนอรวมกับการรีแฟกเตอร์** แยกเป็นข้อต่างหากและติดป้ายว่าเป็นบั๊ก`,
  `     ปนกันเมื่อไหร่ diff จะรีวิวไม่ได้ และตามหาต้นเหตุด้วย bisect ไม่ได้อีกเลย`,
  `  2. **formatter ต้องเป็นข้อเสนอแยกและเป็น commit ของตัวเอง** — commit ที่แตะ 2,000 บรรทัดเพราะจัดรูปแบบ ห้ามมีตรรกะแอบอยู่แม้แต่บรรทัดเดียว`,
  `  3. **โค้ดที่ไม่มีเทสต์คุ้ม ห้ามเสนอให้รีแฟกเตอร์เฉยๆ** — ข้อเสนอต้องรวม "เขียน characterization test คลุมมันก่อน"`,
  `     (characterization test = จับพฤติกรรม **ปัจจุบัน** ไว้ ไม่ใช่พฤติกรรมที่ควรจะเป็น แม้ปัจจุบันจะดูแปลกก็จับไว้ตามนั้น)`,
  `  4. **ข้อเสนอความเร็วต้องมีตัวเลข** ใน \`measured\` — ไม่มีตัวเลข = ไม่ใช่การเพิ่มความเร็ว เป็นความเชื่อ`,
  `  5. **อย่าเสนอเพราะ "มันจะสวยกว่า"** — เขียนใน \`problem\` ให้ได้ว่ารูปทรงปัจจุบัน **ทำให้เกิดอะไรขึ้นจริง**`,
  `     (เช่น "ลิสต์นี้มี 4 สำเนา แก้ที่เดียวลืมอีกสาม" ไม่ใช่ "ควรรวมเป็นที่เดียวจะสวยกว่า")`,
  ``,
  `═══ กฎเหล็ก (Nick #16 — เหตุ 70-agent 2026-06-13) ═══`,
  `  • ❌ **ห้ามเรียก Agent/Task tool · ห้าม spawn subagent** — คุณทำงานคนเดียวทั้งบริษัท`,
  `  • ❌ **ห้ามแก้/เขียน/ลบไฟล์ใดๆ ทั้งสิ้น** — ทริกเกอร์นี้จบที่รายงาน คุณเสนอ Nick ตัดสิน`,
  `  • ✅ ใช้ Read / Grep / Glob + **Bash แบบอ่านอย่างเดียว** ได้: \`git log/diff/show/grep\`, \`ls\`, \`wc\`, \`node --check\``,
  `  • ⛔ \`import\` โมดูล = รัน top-level ของมัน (สร้างโฟลเดอร์ เปิดไฟล์ ต่อ DB ยิงเน็ตได้) — **ไม่ใช่การอ่านอย่างเดียว**`,
  `    อยากดูค่าจริงของฟังก์ชัน → คัดตัวฟังก์ชันมาวางใน snippet เปล่าแล้วรัน ไม่แตะโมดูลจริง`,
  `  • ❌ ห้ามรันชุดเทสต์เต็ม/build/ติดตั้ง/ยิงเน็ต — Coddy ทำให้แล้ว (ดู baseline ข้างบน)`,
  ``,
  `═══ บังคับ: ช่อง \`notCovered\` ═══`,
  `เขียนตรงๆ ว่าอะไรในชั้นนี้ที่คุณ **ไม่ได้ดู** หรือดูแบบผ่านๆ พร้อมเหตุผล`,
  `ตัดขอบเขตไม่ใช่ความผิด — **ตัดแล้วไม่บอกคือความผิด** ความเงียบจะถูกอ่านว่า "ดูแล้วไม่มีปัญหา"`,
  `ดูครบจริง → เขียนว่า "อ่านครบทุกไฟล์ในชั้นนี้" · ❌ ห้ามเว้นว่าง`,
  ``,
  `เรียงข้อเสนอจาก "คุ้มที่สุด" (ผลดีมาก ความเสี่ยงต่ำ) ไปหาคุ้มน้อยสุด · ❌ ห้าม pad ข้อเล็กๆ ให้ดูเยอะ`,
  ``,
  `═══ 📏 งบความยาว — อ่านก่อนเริ่มเขียนผลลัพธ์ ═══`,
  `**ผลลัพธ์ทั้งก้อนต้องไม่เกิน ~30 KB** · เกินแล้วมันจะถูกตัดกลางประโยค กลายเป็น JSON ที่อ่านไม่ออก`,
  `แล้ว **ทั้งบริษัทของคุณจะหายไปจากรายงาน** — งานที่ทำมาทั้งหมดสูญเปล่า ไม่มีใครได้อ่านสักบรรทัด`,
  `(เกิดขึ้นจริง 2026-08-27 กับทริกเกอร์พี่น้องกัน: 2 ใน 3 บริษัทส่ง 36-68 KB แล้วตายทั้งคู่)`,
  `  • ทุกช่องมี \`maxLength\` ผูกไว้ **เขียนให้อยู่ในนั้นตั้งแต่แรก** อย่าเขียนยาวแล้วหวังว่าจะผ่าน`,
  `  • **ตัดคำ ไม่ใช่ตัดงาน** — ดูให้ครบทั้ง 3 มุมเหมือนเดิม แค่รายงานให้กระชับ`,
  `  • ข้อเสนอเกิน 15 ข้อ: ยื่นที่คุ้มที่สุด 15 ข้อ แล้ว **นับที่เหลือลง \`notCovered\`** ห้ามหายเงียบ`,
  `  • \`layerBoundary\` เป็นช่องเดียวที่ยาวได้เต็มที่ — มันคือสัญญาที่ห้ามขยับ ขาดไปข้อเดียวคือแก้แล้วพัง`,
].join('\n')

phase('วิเคราะห์')

// ⛔ เป๊ะ 3 บริษัท — parallel ครั้งเดียว ทุกบริษัทได้ prompt เหมือนกันต่างแค่ชื่อ
const FIRMS = ['A', 'B', 'C']
const rawReports = await parallel(FIRMS.map(f => () =>
  agent(buildPrompt(f), { label: `บริษัท ${f}`, phase: 'วิเคราะห์', schema: REPORT })
))

// ประทับชื่อบริษัทจากลำดับที่สคริปต์รู้ ไม่ใช่ค่าที่ agent พิมพ์กลับมา (บทเรียน 2026-08-27)
const reports   = FIRMS.map((f, i) => rawReports[i] ? { ...rawReports[i], firm: f } : null).filter(Boolean)
const deadFirms = FIRMS.filter((f, i) => !rawReports[i])
const degraded  = reports.length < FIRMS.length

// ── จับคู่ข้อเสนอข้ามบริษัท: ไฟล์ + บรรทัดใกล้กัน + ข้อความทับกันพอ ──
const norm = s => String(s || '').toLowerCase().replace(/\s+/g, ' ').trim()
const normPath = s => String(s || '').toLowerCase().replace(/\\/g, '/').replace(/[^a-z0-9/._-]+/g, '')
const samePath = (a, b) => { if (!a || !b) return false; if (a === b) return true; const A = '/' + a, B = '/' + b; return A.endsWith(B) || B.endsWith(A) }
const locOf = s => {
  const head = String(s || '').trim().split(/\s+[@(—·]|\s{2,}/)[0].trim()
  const m = head.match(/^(.*?):(\d+)/)
  return m ? { path: normPath(m[1]), line: parseInt(m[2], 10) } : { path: normPath(head.split(':')[0]), line: null }
}
const NEAR = 40
const sameSpot = (a, b) => {
  const x = locOf(a), y = locOf(b)
  if (!x.path || !samePath(x.path, y.path)) return false
  return (x.line !== null && y.line !== null) ? Math.abs(x.line - y.line) <= NEAR : true
}
// ไทยไม่เว้นวรรคระหว่างคำ → ตัดเป็น 3-gram (บทเรียน 2026-08-27 จาก reviver)
const hasThai = s => /[฀-๿]/.test(String(s || ''))
const toks = s => {
  const t = norm(s)
  if (!hasThai(t)) return new Set(t.split(/[^a-z0-9]+/).filter(w => w.length > 2))
  const th = t.replace(/[^฀-๿a-z0-9]+/g, '')
  const out = new Set()
  for (let i = 0; i + 3 <= th.length; i++) out.add(th.slice(i, i + 3))
  return out
}
const overlap = (a, b) => {
  const A = toks(a), B = toks(b)
  if (!A.size || !B.size) return 0
  let n = 0; for (const x of A) if (B.has(x)) n++
  return n / ((A.size + B.size) / 2)
}
const SAME_IDEA = 0.18

const all = reports.flatMap(r => (r.proposals || []).map(p => ({ ...p, firm: r.firm })))
const clusters = []
for (const p of all) {
  const hit = clusters.find(c =>
    c.members.some(m => sameSpot(m.file, p.file) && m.aspect === p.aspect &&
      (overlap(m.title, p.title) >= SAME_IDEA || overlap(m.problem, p.problem) >= SAME_IDEA)))
  if (hit) { hit.members.push(p); hit.firms.add(p.firm) } else clusters.push({ members: [p], firms: new Set([p.firm]) })
}

const tiered = clusters.map(c => {
  const n = c.firms.size
  return {
    firms: [...c.firms].sort(),
    agreedBy: n,
    tier: n >= 3 ? 'DO — 3 บริษัทเห็นตรงกัน เป็นปัญหาโครงสร้างจริง'
        : n === 2 ? 'ADJUDICATE — 2 บริษัท: Coddy ต้องเปิดโค้ดตัดสินก่อนเสนอ'
                  : 'LOG ONLY — บริษัทเดียว อาจเป็นรสนิยม ห้ามเสนอให้ทำจนกว่า Coddy จะพิสูจน์ว่าเป็นโครงสร้าง',
    aspect: c.members[0].aspect,
    file: c.members[0].file,
    titles: c.members.map(m => `${m.firm}: ${m.title}`),
    problem: c.members[0].problem,
    proposal: c.members[0].proposal,
    behaviourProof: c.members.map(m => `${m.firm}: ${m.behaviourProof}`),
    blastRadius: c.members.map(m => m.blastRadius).filter(Boolean),
    coveredByTests: c.members.map(m => m.coveredByTests).filter(Boolean),
    measured: c.members.map(m => m.measured).filter(Boolean),
  }
}).sort((a, b) => b.agreedBy - a.agreedBy)

// ข้อเสนอที่ตอบ behaviourProof ไม่ได้ = ไม่ใช่ข้อเสนอของ clean
const noProof = all.filter(p => !String(p.behaviourProof || '').trim())

const thoroughness = reports.map(r => ({
  firm: r.firm,
  proposals: (r.proposals || []).length,
  boundaryStated: !!String(r.layerBoundary || '').trim(),
  testCoverageStated: !!String(r.testCoverage || '').trim(),
  gaps: [
    !String(r.layerBoundary || '').trim() ? 'ไม่ได้เขียน layerBoundary — บอกไม่ได้ว่าอะไรคือสิ่งที่ห้ามขยับ' : null,
    !String(r.testCoverage || '').trim() ? 'ไม่ได้บอกว่าส่วนไหนมีเทสต์คุ้ม' : null,
  ].filter(Boolean),
}))

log(`clean เสร็จ: ${reports.length}/${FIRMS.length} บริษัท` +
    `${degraded ? ` (ขาด ${deadFirms.join(', ')})` : ''} · ข้อเสนอ ${all.length} → ${tiered.length} กลุ่ม · ` +
    `ตรงกัน 3 บริษัท ${tiered.filter(t => t.agreedBy >= 3).length} · 2 บริษัท ${tiered.filter(t => t.agreedBy === 2).length} · เดี่ยว ${tiered.filter(t => t.agreedBy === 1).length}`)

// ⚠ `maxItems: 15` แก้ปัญหา JSON ขาด แต่เปิดปัญหาใหม่: บริษัทที่เจอ 20 ข้อจะยื่น 15 แล้ว "15" อ่าน
// เหมือนจำนวนเต็ม = ตัดขอบเขตเงียบ · prompt สั่งให้นับที่เหลือลง notCovered แต่คำสั่ง ≠ กลไก → ชักธงไว้
const PROPOSALS_CAP = 15
const capHit = reports.filter(r => (r.proposals || []).length >= PROPOSALS_CAP)
  .map(r => `บริษัท ${r.firm} (${(r.proposals || []).length}/${PROPOSALS_CAP})`)

return {
  layer,
  agentsExpected: FIRMS.length,
  agentsUsed: reports.length,        // จำนวนที่คืนผลจริง — ❌ ห้ามเปลี่ยนเป็น FIRMS.length
  degraded,
  deadFirms,
  crossCheckValid: reports.length >= 2,
  capHit,
  capWarning: capHit.length
    ? `⚠ ${capHit.join(' · ')} ยื่นชนเพดานพอดี — ตัวเลขนี้อาจคือ "เท่าที่ยื่นได้" ไม่ใช่ "ทั้งหมดที่เจอ" ` +
      '· อ่าน notCovered ของบริษัทนั้นก่อนสรุปจำนวน'
    : '',
  degradedWarning: degraded
    ? `ได้ผลแค่ ${reports.length}/${FIRMS.length} บริษัท (ขาด ${deadFirms.join(', ')}) — ` +
      (reports.length >= 2
        ? 'ระดับ "ตรงกัน 3 บริษัท" เกิดขึ้นไม่ได้ในรอบนี้ อย่าอ่านว่ามีข้อไหนได้ฉันทามติ'
        : 'เหลือบริษัทเดียว = **ไม่มีการตรวจทาน** ทุกข้อเป็นความเห็นเดี่ยว = รสนิยมล้วน รายงาน Nick ว่ารอบนี้ใช้ไม่ได้')
    : '',

  safety: { backup, branch, baseline },

  // 🧹 ผลของ tidy.mjs — โฟลเดอร์ ไม่ใช่โค้ด · ไม่มี agent ตัวไหนเกี่ยวข้องกับบรรทัดพวกนี้
  housekeeping: housekeeping || '(ไม่ได้รัน)',
  housekeepingWarning: housekeeping ? '' :
    '⚠ ไม่ได้รัน `node tidy.mjs --project <proj>` ในรอบนี้ — รายงานโฟลเดอร์เลยว่างเปล่า ' +
    'ว่างเพราะ "ไม่ได้ดู" ไม่ใช่ "ดูแล้วสะอาด" (บทเรียนเดียวกับ notCovered) · รันแล้วรายงานเพิ่มได้ ฟรี ไม่ต้องรัน clean ใหม่',
  boundaries: reports.map(r => ({ firm: r.firm, layerBoundary: r.layerBoundary })),
  testCoverage: reports.map(r => ({ firm: r.firm, note: r.testCoverage || '(ไม่ได้ระบุ)' })),
  formatter: reports.map(r => ({ firm: r.firm, note: r.formatter || '(ไม่ได้ระบุ)' })),

  proposals: tiered,
  proposalsWithoutProof: noProof.map(p => ({ firm: p.firm, file: p.file, title: p.title })),
  thoroughness,
  notCovered: reports.map(r => ({ firm: r.firm, notCovered: r.notCovered || '(ไม่ได้ระบุ)' })),
  fullReports: reports,

  next: (degraded && reports.length < 2 ? [
    `🛑 STOP (#16): ได้ผลแค่ ${reports.length}/${FIRMS.length} บริษัท — การตรวจทานไม่ได้เกิดขึ้น`,
    'ช่องที่ว่างแปลว่า "ไม่ได้ดู" ไม่ใช่ "ดูแล้วสะอาด" · วินิจฉัย 0 agent ก่อน (failures/journal)',
    'รายงาน Nick ว่ารอบนี้ล้ม แล้วรอให้เขาพิมพ์ trigger ใหม่ · ❌ ห้ามยิงซ้ำเอง (1 trigger = 1 launch)',
  ] : [
    '⛔ **ทริกเกอร์นี้จบตรงนี้ — Coddy ห้ามไหลไปแก้โค้ดต่อเอง** (ต่างจาก Tester #5)',
    'Coddy ทำต่อด้วย 0 agent:',
    '1) `proposals` เรียงตามระดับการเห็นตรงกันแล้ว — **DO (3 บริษัท)** เชื่อได้ · **ADJUDICATE (2)** เปิดโค้ดตัดสินเอง · **LOG ONLY (1)** ห้ามเสนอจนกว่าจะพิสูจน์ว่าเป็นโครงสร้างไม่ใช่รสนิยม',
    '2) `proposalsWithoutProof` — ข้อที่ตอบไม่ได้ว่าจะพิสูจน์ยังไงว่าพฤติกรรมไม่เปลี่ยน **ตัดทิ้ง อย่าเอาไปเสนอ Nick**',
    '3) `boundaries` — 3 บริษัทเขียน "ขอบข้างนอก" ตรงกันไหม ถ้าไม่ตรง แปลว่าเข้าใจชั้นนี้ไม่ตรงกัน ต้องเคลียร์ก่อน',
    '4) `notCovered` ทุกบริษัท ต้องอยู่ในรายงานถึง Nick ด้วย — ส่วนที่ไม่ได้ดู ไม่เท่ากับส่วนที่สะอาด',
    '5) เขียนรายงาน: ข้อเสนอเรียงตามความคุ้ม + blast radius + วิธีพิสูจน์ + สิ่งที่ไม่ได้ดู + บิลโทเค้น (#26.1)',
    '   🧹 **ใส่ `housekeeping` ลงในรายงานเดียวกันด้วย** (#6/#7 · Nick 2026-08-28 — โค้ดกับโฟลเดอร์จบในคำสั่งเดียว)',
    '      แยกหัวข้อให้ชัดว่าอันไหนคือ "รูปทรงโค้ด" อันไหนคือ "บ้านรก" — คนละเรื่อง คนละความเสี่ยง คนละการอนุมัติ',
    '      ❌ ห้ามลบอะไรเอง: ไฟล์บันทึกเกินโควตา **ย้าย** ด้วย `tidy.mjs --rotate` · การเทถังต้องให้ Nick เติม `--yes` เอง ทีละโปรเจค',
    '6) **แล้วหยุด รอ Nick สั่งว่าจะเอาข้อไหน** — ถ้าเขาสั่งให้ทำ: แก้ทีละข้อ รันเทสต์หลังทุกข้อ',
    '   เขียวเก็บเป็น 1 commit · แดง revert ข้อนั้นทิ้งแล้วไปข้อถัดไป · ❌ ห้ามแก้รวดเดียวทั้งก้อน',
    '7) ด่านจบตอนแก้เสร็จ: เทสต์เขียว **และจำนวนเทสต์ไม่ลดลง** · layerBoundary เหมือนเดิมเป๊ะ · formatter รันซ้ำแล้วไม่มีอะไรเปลี่ยน · ตัวเลข perf ก่อน/หลังถ้ามีการอ้าง',
    '8) ❌ ไม่ auto-merge ไม่ auto-build ไม่อัพขึ้น Play — Nick ตัดสินใจ merge เอง',
  ]).join('\n'),
}
