# Case-study tests

These tests bind the package to **one** delivery: the Sistelo AOI, DGT's 1 km lattice over
mainland Portugal, and the numbers in this repository's `README.md` and `docs/live-smoke.md`.
They are evidence that the published run is the run described, not tests of the package.

Everything in `tests/` outside this directory is site-independent and must pass on any
classified LAS/LAZ in a projected metric CRS.

That last sentence is the **contract** the split establishes, not a measurement. What has been
measured is narrower and worth stating plainly: the generic half passes with `aoi/aoi.geojson`
removed from the tree, and the case-study half fails without it. Those two runs are what make the
boundary real rather than declared. Running on someone else's delivery remains UNVALIDATED until
someone exercises it — DGT is the one provider this package has been run against.

**Forking this for your own data:** delete this directory. If anything in `tests/` then fails,
that is a real coupling and a bug — please report it.
