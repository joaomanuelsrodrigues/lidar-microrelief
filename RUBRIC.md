# Pre-registered rubric

Committed before the first line of pipeline code. An independent reader answers these
**from the repository** — code and outputs, not the README.

1. **Ground filtering.** Which filter, which parameters, **why those values**, and what is the
   agreement with the official classification, reported **per class with the majority-class null
   beside it**?
2. **Common grid.** Where is it defined, and can you show that no elementwise arithmetic ever
   happens between per-tile windows?
3. **Voids.** What fraction of the DTM is `measured` / `interpolated` / `undetermined`, and what is
   the **closed-form expectation** given the measured density and the cell size?
4. **Provenance and reproducibility.** Do two runs produce identical bytes? Can a stranger reproduce
   from the record alone? Does the CC-BY attribution reach the consumer?
5. **Refusals.** Name three inputs the pipeline refuses, and show the refusal with the reason in
   the message.

**Bar:** failure = **≥1 question unanswerable from code + outputs**, OR an answer that
**contradicts the README**. On failure: fix, or drop this piece for the STAC library. Do not
publish and hope.

**Self-check before calling the judge:** a 10-minute explanation using numbers from our own run.
Any answer of the form *"I used the published raster"* or *"I did not verify"* fails, and does not
reach the judge.
