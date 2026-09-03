# Sistelo sample

150 m × 150 m of raw DGT LiDAR around the tallest verified terrace riser at Sistelo, cut from tile
`LO-179557-07-2025` with `scripts/make_sample.py` (window −20210…−20060 × 256245…256395, EPSG:3763).
Nothing about the returns was changed; the header was recomputed for the cut.

- Points: 390,450 · size: 3,174,006 bytes · sha256:
  `9d65a09170f7085263d933c1d04a08a302db274a41d89b27983500755269202b`
- Source: Direção-Geral do Território, Centro de Dados, LiDAR point clouds — **CC BY 4.0**. Derived
  products are not reviewed or endorsed by DGT (`../../ATTRIBUTION.md`).
- `expected/` holds the record and per-band digests from the author's run. On every CI run the
  test suite reproduces the record (an assertion) and compares the six band digests (a warning
  until the probe is promoted; it has been silent on GitHub's runner since 2026-08-26).
- Size cap: 6,000,000 bytes, locked by `tests/test_sample.py` — a first run should not start with a
  download. The cap and the window are the only numbers this directory introduces.

Run it:

    uv run microrelief run --aoi examples/sistelo-sample/aoi.geojson --laz examples/sistelo-sample \
        --out outputs/sample --attribution "$(cat examples/sistelo-sample/attribution.txt)"

What comes out, on the author's machine: a 300 × 300 grid of 0.5 m cells; basis 51.6% measured ·
42.3% interpolated · 6.1% undetermined; measured density 17.3 pts/m²; record hash `2da06987808e`.
Without `--selection` (the DGT catalogue step) the record says it does not know what the provider
claimed — `flight_date` and `point_count_catalogue` are `null` — rather than repeating what it
measured.

## Header

The LAZ is binary, so the repository's text gate cannot read it. These are its free-text fields,
printed and read before the file was committed — provider and software names only:

    system_identifier = 'AL;'
    generating_software = 'TerraScan'
    vlr[0] LASF_Projection · vlr[1] LASF_Projection · vlr[2] LASF_Spec 'RIEGL Extra Bytes'
    vlr[3] LASF_Spec · vlr[4] LASF_Spec 'TerraScan Extra Bytes' · vlr[5] laszip encoded 'http://laszip.org'
