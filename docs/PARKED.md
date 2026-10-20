# What is actually open — Happy Photo Organizer

**Written 2026-10-20 for the Director handover.** One screen, so nobody has to
reconstruct it from seventeen addenda in `CHAIN_CHECKLIST.md`. **Current state
only — the reasoning lives in the addenda this points at.**

Everything below is in git. **Nothing of this project exists only in a session.**

---

## 🔴 Waiting on Nick

| # | Item | What a decision unblocks | Where |
|---|---|---|---|
| 1 | **Agent-cap hook: the loop gap.** `for`/`while` calling `agent()` directly is not blocked — 40 agents pass with `MAX_AGENTS: 3` declared. | Tighten it, or reword `CLAUDE.md` #16.1 so a reader does not count less carefully on the strength of it. **JobShot tightened theirs on Nick's instruction to them; I have not acted on a relayed instruction.** | `AGENT_CAP_HOOK_AUDIT.md` |
| 2 | **Agent-cap hook: a false reason.** A named-array fan-out is refused with *"fans out over runtime data via `.map()`"* — the decision is right, the sentence is false, and it sends the reader hunting for runtime data in a literal array. | Same guard, so bundled with #1 rather than done separately. JobShot has fixed theirs and left the hard part written down: blank strings and comments **before** matching, keep template `${…}` holes, test the stripper. | same |

**Both are changes to the enforcement of a rule in `CLAUDE.md`, so a peer's
suggestion is not grounds to make them.** They are scoped and ready; one word
starts them.

---

## 🟡 Needs all three projects + a version on the sheet

| Item | State |
|---|---|
| **LAN_PROTOCOL v1.2** — `revision`, `removed`, `photo_id` for correcting a job's **photographs** | Designed and agreed in principle by all three (§3 addenda 8–10). **Not started by anyone.** Deliberately sequenced after the sidecar route. |
| **A machine identity in the §2 ping reply** | **The gap that cost a week.** HPO's ping prints `ship` and no host; JobShot's `Receipt` carries no PC identity at all, while every string in their app says *"the PC"*. **One printed an identity nobody read, one never printed one** — which is why two installations on one LAN stayed invisible for days. My half is cheap and additive; theirs has to persist it. **Neither of us has built it, and neither has been asked to.** |

---

## ✅ Closed — recorded here because the handover note still lists one of them as open

| Item | Ruling |
|---|---|
| **§6.1 — the vessel guard** (refusing a manifest with no `ship`) | **CLOSED by Nick, 2026-10-02. Not shipping, and should not.** *"มันจะข้ามเรือได้ไง ก็สเกนจับคู่อยู่แล้ว และทำงานในวงแลนเท่านั้น"* — the token is per-PC and the socket binds to the LAN interface, both measured, so a job cannot arrive from another vessel over Wi-Fi at all. Shipping it would refuse input accepted today for no gain. §3 addendum 14, and `CHAIN_CHECKLIST.md:1251`. **The 2026-10-20 Director handover lists this as still waiting on Nick; it is not.** |
| §5.6 — the full-month day rule | Already correct before I asked. `monthrange()`, real calendar per month. |
| `filed.date_was_capped` | Shipped v1.059 on Nick's approval. |
| The vessel-**crossing** test gap | Explained, not outstanding: **this machine is the test installation** (ship `ENA Test`), so of course every job it holds names its own vessel. Addendum 17. |

---

## 📦 The sidecar route — **unused, not unverified**

**Nobody owes anything here.** Nick has never had a job that needed correcting
(*"ยังไม่เคยยิงซ้ำจริงๆสักที"*), so the archive side was never a verification debt —
**it is an unused feature**, and a debt justifies pressing where an unused feature
does not. All three of us had been pressing. §3.6.

| | |
|---|---|
| HPO | implemented v1.060, hardened v1.062 |
| JobShot | built and installed, v0.038+ |
| EMR | v0.4.7 live; v0.4.2 refuses two drafts under one manifest |
| **The real PC** | `DESKTOP-NPAM51V` · `192.168.110.167` · ship **`ENA CHALLENGER`** · **v1.062** |
| **This machine** | ship **`ENA Test`** — the **test** install. Its archive is not Nick's real one. |
| Exercised in anger | **zero.** One cable test, 2026-10-03 06:49:14, on **v1.060** — 44 min before v1.062 existed. |

**Green light given 2026-10-13.** The next correction Nick actually needs will be
the first real use, and the folder gets read afterwards as a by-product.

---

## 📤 Handed to the rules session, not to Nick

`memory/TO_PROMOTE.md` — **4 amendments waiting**, per #10.1 (a project-scoped
session may not promote; it hands over). `an-absence-is-not-a-fact` widened to
inference · `a-true-fact-is-not-evidence-for-the-next-thing` ·
`the-unread-field` · `wanting-the-confirmation-is-not-the-user-needing-to-act`.

---

## State of the tree, at the time of writing

    VERSION 1.062, published and verified from outside
    167/167 tests green
    working tree clean, 0 ahead / 0 behind origin
    releases go through tools/publish_release.py — 8 gates, each proven to refuse

— Codey (HPO session)
