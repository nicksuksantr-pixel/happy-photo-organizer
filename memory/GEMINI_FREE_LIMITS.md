# Gemini limits — the free tier, and the house's one paid project (Tier 2), as AI Studio shows them

> Two tiers live in this file: the **free tier** (every free key in the house; sections below) and the **paid Tier 2
> project** that TTVC uses (its own section near the end, measured 2026-11-02). Rule #2.1 still stands: a paid key is
> never built into an app and never borrowed by another project (#2); its numbers are here so a session can plan.

> **Measured 2026-11-01** from three screenshots Nick took of https://aistudio.google.com/rate-limit for one free key
> (afternoon, Thai time). The **limit** half of every cell is the free tier's cap: it is set per Google Cloud project,
> so every free key in the house sees the same numbers until Google changes them. The **used** half was that key's day
> at the moment of the screenshot; it is kept here only as an example of what unguarded calls do (see "What the numbers
> say"). The docs page (ai.google.dev/gemini-api/docs/rate-limits) does not print per-model numbers; AI Studio does,
> behind the key owner's login, which is why this file exists.
>
> **How to use it (command_pattern #2):** before an app's first call, copy THAT model's row with the date into the
> app's memory and into the small file its gate reads; put a per-minute gate and a per-day counter in front of every
> call. When AI Studio shows other numbers later, update this file with the new date (a screenshot from Nick, or a
> session's own read of its key's page) and the sync carries it to every repo's `memory/`.
> Model ids in the last column are the ones NP verified with real calls on 2026-10-31/11-01; a blank means not verified.

## Text models

| Model (AI Studio name) | RPM | TPM | RPD | Used that day | API id |
|---|---|---|---|---|---|
| Gemini 3.5 Flash Lite ⭐ house default | **15** | **250K** | **500** | 15 / 64.09K / 115 | `gemini-3.5-flash-lite` |
| Gemini 3.1 Flash Lite | 15 | 250K | 500 | 10 / 29.02K / 25 | `gemini-3.1-flash-lite` (shuts down 2027-05-07) |
| Gemini 3.8 Flash (newest Flash) | 5 | 250K | **20** | 2 / 16 / 5 | `gemini-3.8-flash` |
| Gemini 3.6 Flash | 5 | 250K | **20** | 5 / 1.38K / 18 | `gemini-3.6-flash` |
| Gemini 3 Flash (preview) | 5 | 250K | **20** | 6 / 1.64K / **38** | `gemini-3-flash-preview` |
| Gemini 2.5 Flash | 5 | 250K | **20** | 3 / 822 / **21** | `gemini-2.5-flash` |
| Gemini 2.5 Flash Lite | 10 | 250K | 20 | 0 | `gemini-2.5-flash-lite` — answers 404 for new users (NP, 2026-11-01) |
| Gemma 4 31B | 30 | **16K** | **14.4K** | 1 / 5 / 1 | `gemma-4-31b-it` |
| Gemma 4 26B | 30 | 16K | 14.4K | 0 | `gemma-4-26b-a4b-it` |
| Gemini Robotics ER 2 Preview | 5 | 250K | 20 | 0 | |
| Antigravity (Agents) | 60 | 100K | 100 | 0 | |

## Speech, audio, embeddings

| Model | RPM | TPM | RPD | Used that day | Speaks Thai | API id |
|---|---|---|---|---|---|---|
| Gemini 3.8 Flash TTS | 3 | 10K | **10** | 3 / 365 / **18** | ✔ (docs table, live page 2026-11-01) | `gemini-3.8-flash-tts` (no shutdown date) |
| Gemini 3.8 Flash Lite TTS | 3 | 10K | 10 | 0 | **— no Thai** (docs table, live page 2026-11-01) | `gemini-3.8-flash-lite-tts` |
| Gemini 3.1 Flash TTS | 3 | 10K | 10 | 0 | ✔ (TTVC probe, Aoede fallback) | `gemini-3.1-flash-tts-preview` (shuts down 2026-11-17) |
| Gemini 2.5 Flash TTS | 3 | 10K | 10 | 0 | ✔ (TTVC probe, Aoede fallback) | `gemini-2.5-flash-preview-tts` (shuts down 2026-11-17) |
| Gemini 3.5 Transcribe | 3 | 10K | 25 | 0 | `gemini-3.5-transcribe` |
| Gemini Embedding 1 | 100 | 30K | 1K | 0 | `gemini-embedding-001` |
| Gemini Embedding 2 | 100 | 30K | 1K | 0 | `gemini-embedding-2` |

## Live API (no request caps shown, only tokens per minute)

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemini 2.5 Flash Native Audio Dialog | Unlimited | 1M | Unlimited |
| Gemini 3 Flash Live | Unlimited | 65K | Unlimited |
| Gemini 3.8 Live · Gemini 3.8 Live Extended Thinking | Unlimited | 65K | Unlimited |
| Gemini 3.5 Live Translate · Gemini 3.5 Transcribe Live | Unlimited | 20K | Unlimited |

## 0 on the free tier (paid only, or not open to this key)

Gemini 4 Argon · Gemini 3.1 Pro · Gemini 2.5 Pro · Gemini 2.5 Pro TTS · Gemini 2 Flash · Gemini 2 Flash Lite ·
Deep Research Pro Preview · Computer Use Preview · Gemini Omni 1.1 Flash · every image model (Nano Banana: 2.5 Flash
Preview Image, Pro / 3 Pro Image, 2 / 3.1 Flash Image, 2 Lite / 3.1 Flash Lite Image, 2.1) · Lyria 3 Clip · Lyria 3 Pro ·
Veo 3 Fast Generate · Veo 3 Generate · Veo 3 Lite Generate (the Veo rows show no TPM at all).

## Tools (grounding)

| Tool | Models | RPD |
|---|---|---|
| Map grounding | every model listed (2 Flash … 4 Argon, Robotics ER 2) | **0** on this key |
| Search grounding | Gemini 2 · Gemini 2.5 · "Default" | 1.5K each |
| Search grounding | Gemini 3 and newer | **0** |

## Paid tier — Tier 2, the house's one paid project ("Gemini Project", TTVC's key), measured 2026-11-02

> Nick's four screenshots of the same AI Studio page for the paid project (header "Tier 2", time range 90 days; the
> used column is that project's 90-day peak). TTVC is the only project on it (`GEMINI_VIDEO_API_KEY`, TTVC's
> `docs/GEMINI_FREE_KEY.md` §5). Transcribed by the Director and checked by an independent read. Google can change
> the tier's numbers without notice; re-read the page before planning a big batch.

| Model | RPM | TPM | RPD | 90-day peak use |
|---|---|---|---|---|
| Gemini 2 Flash · 2 Flash Lite | 10K · 20K | 10M | Unlimited | 0 |
| Gemini 2.5 Flash Lite | 10K | 10M | Unlimited | 0 |
| Gemini 3.5 Flash Lite · 3.1 Flash Lite | 10K | 10M | 350K | 0 |
| Gemini 3.8 Flash · 3.6 Flash · 3 Flash · 2.5 Flash | 2K | 3M | 100K | 0 |
| Gemini 4 Argon | 2K | 8M | Unlimited | 0 |
| Gemini 3.1 Pro · 2.5 Pro | 1K | 5M | 50K | 0 |
| Computer Use Preview | 1K | 5M | 50K | 0 |
| Gemini Robotics ER 2 Preview | 2K | 3M | 100K | 0 |
| Gemini Embedding 1 · 2 | 5K | 5M | Unlimited | 0 |
| Gemma 4 26B · 31B | 30 | 16K | 14.4K | 0 (same as the free tier) |
| Gemini 3.8 Flash TTS · 3.8 Flash Lite TTS · 3.1 Flash TTS · 2.5 Flash TTS | 1K | 100K | 10K | 3.8 Flash TTS: 2 / 61 / 5 |
| Gemini 2.5 Pro TTS | 250 | 25K | 2.5K | 0 |
| Gemini 3.5 Transcribe | 1K | 100K | 10K | 0 |
| Nano Banana (2.5 Flash Preview Image) | 2K | 1.5M | 50K | 0 |
| Nano Banana Pro (3 Pro Image) · Nano Banana 2 Lite (3.1 Flash Lite Image) | 500 | 500K | 15K | 0 |
| Nano Banana 2 (3.1 Flash Image) · Gemini Nano Banana 2.1 | 500 | 1M | 10K | Nano Banana 2.1: 5 / 13.16K / 73 |
| Gemini Omni 1.1 Flash | **8** | Unlimited | **100** | 5 / 61.14K / **27** |
| Lyria 3 Clip · Lyria 3 Pro | 500 | 10M | 10K | 1 / 167–337 / 2 |
| Veo 3 Fast Generate · Veo 3 Generate · Veo 3 Lite Generate | **4** | — | **50** | 0 |
| Live API: 2.5 Flash Native Audio Dialog | Unlimited | 10M | Unlimited | 0 |
| Live API: 3 Flash Live · 3.8 Live | Unlimited | 400K | Unlimited | 0 |
| Live API: 3.8 Live Extended Thinking | Unlimited | 600K | Unlimited | 0 |
| Live API: 3.5 Live Translate · 3.5 Transcribe Live | Unlimited | 300K | Unlimited | 0 |
| Antigravity (Agents) | 200 | 300K | 10K | 0 |
| Deep Research Pro Preview (Agents) | 10 | 10M | 14.4K | 0 |

Tools on Tier 2: **Search grounding** 5K a day on Gemini 2 / 2.5 / Default and **1.5K a day on Gemini 3 and newer**
(0 on the free tier) · **Map grounding 25K a day on every model** (0 on the free tier).

What the paid numbers say:
1. **Everything the free tier shows as 0 opens here**: the image models, Veo, Lyria, Omni, the Pro models, Deep Research, Computer Use, grounding on Gemini 3+.
2. **The tight ones are still tight**: Veo 3 is **4 a minute, 50 a day** per model; Omni 1.1 Flash is **8 a minute, 100 a day** (TTVC's 90-day peak already used 27 of them in one day); Deep Research 10 a minute. A video or lip-sync batch is planned against those, not against "paid = unlimited".
3. **Gemma 4 does not change with the tier** (30 / 16K / 14.4K on both).
4. **TTS is 1K a minute, 10K a day per model** here, against 3 / 10K / 10 on a free key: a paid key is the road for any voice work that outgrows ten lines a day — and it stays TTVC's, never built into an app (#2.1) and never borrowed (#2).
5. Text models: Flash-Lite 10K RPM / 350K a day; Flash 2K / 100K; Pro 1K / 50K; the 2.x models and Gemini 4 Argon have no daily cap.

## Shutdowns that matter (deprecations page, last updated 2026-10-22, read 2026-11-01)

The page's own caveat: the dates are the earliest a model might be retired.

| Date | Model | Replacement Google names |
|---|---|---|
| 2026-11-17 | `gemini-3.1-flash-tts-preview` · `gemini-2.5-flash-preview-tts` · `gemini-2.5-pro-preview-tts` | `gemini-3.8-flash-tts` or `gemini-3.8-flash-lite-tts` (the Lite one has no Thai) |
| 2026-11-17 | `gemini-3.1-flash-live-preview` · `gemini-2.5-flash-native-audio-preview-12-2025` | `gemini-3.8-live` |
| 2027-05-07 | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` |
| none announced | `gemini-3.8-flash-tts` · `gemini-3.8-live` | — |

## What the numbers say (for the code)

1. **Only the Flash-Lite models have a daily budget worth batching on: 500.** Every non-Lite Flash (3, 3.6, 3.8, 2.5)
   is **20 requests a day, 5 a minute**. A fallback chain that ends on a Flash model lands in a 20-a-day bucket, so
   bulk work must stay on Flash-Lite and use Flash only for the few calls that need it.
2. **TTS is 10 requests a day per TTS model, 3 a minute, 10K tokens a minute.** Four buckets exist today; two of them
   (3.1 Flash TTS, 2.5 Flash TTS) shut down on 2026-11-17, leaving 3.8 Flash TTS + 3.8 Flash-Lite TTS = **20 TTS
   calls a day on a free key, in total — for a language both of them speak.** **3.8 Flash-Lite TTS has no Thai**
   (Google's language table, row "Thai": Flash TTS ✔, Flash-Lite TTS —; read on the live page 2026-11-01 after
   TTVC's correction), so **a Thai project has 10 TTS requests a day on a free key from 2026-11-17.** A program that
   makes Thai voice clips plans its day around ten, and a fallback onto a retired model answers 404, so the chain
   must pass a retired model over instead of crashing (TTVC v0.004 does).
3. **Gemma 4 (31B, 26B) is the high-count model: 14.4K a day, 30 a minute, but only 16K tokens a minute** — many short
   calls, not long documents.
4. **Embeddings: 1K a day, 100 a minute, 30K TPM.** The Live API shows no request caps, only tokens per minute.
5. **The counter keeps counting past the limit.** "38 / 20", "21 / 20" and "18 / 10" in the used column are calls that
   were refused with 429 after the bucket was empty: the key had already gone red. A client-side gate (#2) is what
   keeps the used number at or below the limit; a retry loop only drives it further past.
6. **2.5 Flash Lite shows a quota (10 / 250K / 20) but answers 404** for keys that never used it (Google kept the 2.5
   models for existing users, changelog 2026-09-18). A quota on the page is not proof the model answers.
7. **Grounding on the free tier is Gemini 2 / 2.5 only** (1.5K a day); on Gemini 3 and newer it is 0. Map grounding is
   0 on every model for this key, whatever the pricing page says: **the key's own AI Studio page wins over the pricing
   page** when the two disagree.
8. **Newest family on the free tier is 3.8.** Gemini 4 (Argon) is listed with 0 free quota, so it is paid only.
9. Daily buckets reset at **midnight Pacific** (15:00 Thai from 2026-11-02 to 2027-03-14, then 14:00).
10. **Routed ids and access** (NP's read of the docs, changelog and `models.list`, 2026-11-01; promoted from NP's
    `memory/TO_PROMOTE.md`): `gemini-3.7-flash` is served by `gemini-3.8-flash` and `gemini-3.5-flash` by
    `gemini-3.6-flash`; `gemini-flash-latest` follows the newest Flash (3.8) and `gemini-flash-lite-latest` the newest
    Flash-Lite (3.5). **The 2.5 models are kept only for keys that used them before 2026-09-18**: a new key gets 404 on
    `gemini-2.5-pro` and `gemini-2.5-flash-lite` although the pricing page lists them as free. **Google no longer
    publishes free-tier numbers**: the rate-limits page says to view them in AI Studio, which is why this file exists
    and why "RPM 15 / 250K / 500" was only ever one model's row.

## History

| Date | What | Source |
|---|---|---|
| 2026-05-17 | Flash-Lite 15 / 250K / 500, stated by Nick | Nick's note |
| 2026-08-16 | 3.5 Flash-Lite confirmed at the same limits as 3.1; default moved up | Nick |
| 2026-10-31 | 500 a day for 3.5 Flash-Lite read in AI Studio by Nook | NP |
| 2026-11-01 | Every model's row above | Nick's three screenshots of AI Studio, transcribed by the Director and checked by an independent read |
| 2026-11-01 | TTVC's correction: 3.8 Flash-Lite TTS has no Thai, so a Thai project has 10 TTS a day after 2026-11-17, not 20; the shutdown table | TTVC (`docs/GEMINI_FREE_KEY.md` §4/§6, probes with its own key) · verified by the Director on the live docs page (row "Thai": ✔ / —) and the deprecations page |
| 2026-11-01 | Third independent transcription of the same screenshots (NP, from Nook's copy): 0 differences on 64 rows. Item 10 (routed ids, 2.5 restriction, numbers unpublished) promoted from NP's `memory/TO_PROMOTE.md` | NP (`secretary/work/gemini-free-limits/2026-11-01_ai-studio-rate-limits.md`, `config/gemini_limits.json`) |
| 2026-11-02 | The paid Tier 2 project's table (TTVC's key): "this is the paid one that is available, remember it; TTVC uses it" | Nick's four screenshots of AI Studio, transcribed by the Director and checked by an independent read |
