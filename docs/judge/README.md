# The judge rounds

These files are the verbatim verdicts of an independent LLM judge run against the repository at
fixed commits, under the prompt in `prompt.md`. They are part of the method, not commentary: the
README's claims were checked by something that had not written them, and every contradiction the
judge found is either fixed (with the commit named in the next round) or refuted in writing.

Each round reads the whole tree as it stood. A "clean" round is a sample, not a proof — round 4
found three real contradictions in text round 3 had passed — so the stopping rule was consecutive
frozen rounds with the union of findings verified against the code, never one clean verdict.

**Legend.** `sNNN` in these files and in `docs/live-smoke.md` is the author's working-session
number; the date beside it is the fact. `T-xxx` is the author's task-ledger ID for the change being
judged. Neither points at anything in this repository; both are left as written because these are
dated records, and a record is annotated, never rewritten.

Four more identifier shapes appear in the dated records here and in `docs/live-smoke.md`, and
none of them resolves to anything in this repository either. They are the author's private
working vocabulary, listed so a reader can skip them rather than hunt for a definition:

| shape | what it was | example |
|---|---|---|
| `§A`_n_ | a class in the author's ledger of past failures, cited as the reason for a guard | `§A1`, `§A6` |
| `Task `_n_ | a step of the author's written plan for this repository | `Task 9` |
| `F-0`_nn_ | a numbered finding in the author's method notes | `F-047`, `F-050` |
| `E-00`_n_ | a numbered experiment in the same notes | `E-006` |

Live files — the README, `SITE.md`, `CALIBRATIONS.md`, the source and the tests — say the rule in
plain words instead, so nothing a reader must act on depends on resolving one of these. Where a
dated record above still carries them, that is deliberate: the record is what was written at the
time.
