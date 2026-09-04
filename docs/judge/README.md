# The judge rounds

These files are the verbatim verdicts of an independent LLM judge run against the repository at
fixed commits, under the prompt in `prompt.md`. They are part of the method, not commentary: the
README's claims were checked by something that had not written them, and every contradiction the
judge found is either fixed (with the commit named in the next round) or refuted in writing.

Each round reads the whole tree as it stood. A "clean" round is a sample, not a proof — round 4
found three real contradictions in text round 3 had passed — so the stopping rule was consecutive
frozen rounds with the union of findings verified against the code, never one clean verdict.

**Legend.** `sNNN` in these files is the author's working-session number; the date beside it is
the fact. `T-xxx` is the author's task-ledger ID for the change being judged. Neither points at
anything in this repository; both are left as written here because these files are the judge's
own words at a fixed commit, and quoting a third party means quoting them unedited.

Three more identifier shapes appear in these verdicts, and none of them resolves to anything in
this repository either. They are the author's private working vocabulary, listed so a reader can
skip them rather than hunt for a definition:

| shape | what it was | example |
|---|---|---|
| `§A`_n_ | a class in the author's ledger of past failures, cited as the reason for a guard | `§A1`, `§A9` |
| `Task `_n_ | a step of the author's written plan for this repository | `Task 3` |
| `E-00`_n_ | a numbered experiment in the same notes | `E-006` |

Everywhere else — the README, `SITE.md`, `CALIBRATIONS.md`, the records under `docs/`, the source
and the tests — says the rule in plain words instead, so nothing a reader must act on depends on
resolving one of these. That is enforced rather than asserted: `tests/test_no_private_ids.py`
fails on any of these shapes, plus one this legend no longer lists because it occurs nowhere
here (a finding number, `F-0` and two digits), in any tracked file outside `docs/judge/`. It was written because
the sentence above had been false, with twenty-one occurrences on eighteen lines across seven
files under `src/`, `tests/` and `scripts/`. This directory is the one exemption, and the reason
is the one above: these are somebody else's words.
