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
