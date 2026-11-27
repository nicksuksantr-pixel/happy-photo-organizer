# REPEAT_MISTAKES.md — the mistakes and bugs that came BACK (command_pattern #29)

> Never rotated, never moved to `_trash/`, outside the #7 quota. Injected into every session at start by
> `tools/repeat-mistakes-hook.mjs` (a SessionStart hook in `.claude/settings.json`), so nobody has to remember to read it.
> **A row is added the SECOND time something happens** (or at once when Nick says it is a repeat). Every later repeat bumps
> `Times` and `Last` in the same session. Product bugs AND Coddy's own working slips both count.
> One row = one class of mistake. Keep it short: ≤ 20 active rows, details live in `bug/` and the memory topic files.
> The `Mechanism` column is the goal: a test, hook or gate that fails on its own. A row whose mechanism says
> `reminder only` is the kind that has already failed once — ask every time it repeats: can it get a mechanism now?

| # | Mistake (the class, not one instance) | Times | Last | When it strikes | Do instead | Mechanism |
|---|---|---|---|---|---|---|

## How to use this page
- **Session start:** the hook shows the table above. If today's task touches a row's "when it strikes", say so in the plan.
- **After a repeat:** bump `Times` + `Last` here before the commit (#20.0), and write the instance in `bug/` as usual (#10).
- **Closing a row:** only when its mechanism exists AND it has not repeated for 30 days — move it under `## Closed`, never delete.
- **Would it bite another project?** → `memory/TO_PROMOTE.md` for `SHARED_LESSONS` (#10/#10.1).

## Closed (mechanism holds — kept here, not injected)

| # | Mistake | Times | Closed | Mechanism |
|---|---|---|---|---|
