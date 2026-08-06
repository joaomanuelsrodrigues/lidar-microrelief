You are reviewing the repository you have been given access to. Answer each question below
**from the code and the outputs**, not from the README. For each: quote the file and line that
supports your answer, or state that it is not answerable from the repository.

Then, separately, list any place where the README contradicts what the code or outputs show.

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
