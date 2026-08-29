# Site selection

Criteria fixed on 2026-07-30, **before any candidate was examined**. A site
enters only by passing all four. If none passes, the site is the blocker; the criteria do not move.

| # | Criterion | How it was checked |
|---|---|---|
| 1 | DGT coverage confirmed by a real query | `scripts/triage_candidates.py` against the live catalogue, output pasted below |
| 2 | Canopy present over the terraces | Provisional from public land cover; **confirmed by measurement** — the share of returns above 2 m |
| 3 | Terraces already publicly documented | Named source with a link, per candidate |
| 4 | No sign of non-inventoried structure | Stated explicitly, per candidate |

Criterion 3 is the one that dissolves a tension this project began with: on a landscape that
is **already publicly described**, full reproducibility and prudence stop competing — publishing
the relief reveals nothing that was hidden. Documented is a *pass*, not a disappointment. Criterion
4 is its safeguard: a landscape where structure is actively being found is excluded, however
interesting, because the piece must not be the thing that discloses it.

## Status: **RESOLVED 2026-08-04 — the site is Sistelo, Arcos de Valdevez**

The AOI is `aoi/aoi.geojson`: 1980 m × 1980 m at (-20990, 255010, -19010, 256990) in EPSG:3763
(ETRS89 / PT-TM06), four tiles, all flown **2026-03-30**, 25.1–28.3 pts/m², 845 MB to download.

Two things had to be corrected before the verdict could be written, and both are recorded rather
than folded in silently.

### Correction 1 — the pre-registered expectation about Sistelo was wrong

The 2026-08-02 draft of this file predicted that Sistelo *"is also the one most likely to fail
criterion 1, being in the northwest where the DGT survey is incomplete"*. Measured on 2026-08-04:
**66 tiles over the parish, a complete lattice, no gap.** The prior was reasonable and it was
false. It is left standing above rather than edited out, because a pre-registration that gets
quietly revised to match the data is not a pre-registration.

### Correction 2 — the triage box was not on the site

The Sistelo box first carried in `scripts/triage_candidates.py` was
`(-8.375, 41.930, -8.351, 41.948)`. That box lies **1–3 km south of the Sistelo parish boundary**
and 2.8 km from the village: criterion 1 was being measured somewhere the criterion-3 evidence
does not reach, because the Portaria names the socalcos of the classified landscape, not of that
box. The candidate now *is* the AOI. This moves where a criterion is measured; it does not relax
the criterion, and no candidate's score improved as a result — Sistelo's coverage was already a
pass at the old box.

## Criterion 1 — triage output (verbatim, 2026-08-04)

```
$ PYTHONPATH=src .venv/bin/python scripts/triage_candidates.py
sistelo-arcos-de-valdevez    tiles=  4  epsg=3763  dates=2026-03-30  rho=25.1-28.3 pts/m2  void@f=0.4=8.2%
                             box_in_crs=(-20996, 255010, -19005, 256990)  1991 x 1980 m
                             covered=1.000
                             tile origins=[(-21000, 255000), (-21000, 256000), (-20000, 255000), (-20000, 256000)]
alto-douro-pinhao            tiles=  9  epsg=3763  dates=2024-11-22  rho=15.9-21.2 pts/m2  void@f=0.4=20.3%
                             box_in_crs=(48926, 168032, 50926, 170045)  2000 x 2013 m
                             covered=1.000
                             tile origins=[(47999, 167999), (47999, 168999), (47999, 170000), (48999, 169000), (48999, 169999), (49000, 167999), (49999, 169000), (49999, 169999), (50000, 167999)]
coa-valley                   tiles= 10  epsg=3763  dates=2024-11-11,2024-11-18,2024-12-11  rho=12.6-21.6 pts/m2  void@f=0.4=28.3%
                             box_in_crs=(85989, 156156, 87982, 158179)  1993 x 2023 m
                             SELECTION REFUSED (AOI spans 3 sorties (2024-11-11T00:00:00Z, 2024-11-18T00:00:00Z, 2024-12-11T00:00:00Z); a mosaic of two epochs is a product made of two moments — pass allow_mixed_epochs to accept and declare it)
                             tile origins=[(84999, 156000), (84999, 156999), (84999, 157999), (85999, 156000), (85999, 156999), (85999, 157999), (86999, 156000), (86999, 156999), (86999, 157999), (87999, 156000)]
serra-da-estrela-manteigas   tiles=  9  epsg=3763  dates=2025-07-04  rho=22.3-40.3 pts/m2  void@f=0.4=10.7%
                             box_in_crs=(49930, 80860, 51954, 82873)  2024 x 2013 m
                             covered=1.000
                             tile origins=[(49000, 80000), (49000, 81000), (49000, 82000), (50000, 80000), (50000, 81000), (50000, 82000), (51000, 80000), (51000, 81000), (51000, 82000)]

All 4 candidates measured.
```

All four candidates now have DGT coverage. **Criterion 1 does not separate them** — it only did so
on 2026-08-02, when none of them could be reached at all.

Two things in that table are worth reading carefully. Côa's refusal is not a coverage failure: its
ten tiles were flown on three dates spanning 30 days, and `select_tiles` refuses to register a
30-day mosaic onto one grid without being told to. And Manteigas reads `dates=2025-07-04` only
because sortie grouping was added — the catalogue publishes four stamps for it,
6m23s apart, and before the change it was refused for spanning four "epochs" that are one pass of
one aircraft.

## How criteria 2-4 were scored

Sources were gathered by four independent research assistants, one per candidate, each required to
carry a fetched URL for every claim. **The scoring against the criteria was done by hand, not
taken from those reports.** Three of the four inverted criterion 3 — reading "already publicly
documented" as a weakness ("limited new insight value") rather than as the safeguard it is — and
two inverted criterion 4, treating "archaeologically sensitive and unsurveyed" as a point in a
candidate's favour. The sources they returned were real and checkable; the polarity of the
conclusions on top of them was not. The decisive criterion-3 source below was re-fetched and read
directly rather than accepted second-hand.

## Candidates

### sistelo-arcos-de-valdevez — **CHOSEN**, AOI at (-20990, 255010, -19010, 256990) EPSG:3763

- **Criterion 1 — PASS.** Four tiles, one sortie (2026-03-30), 25.1–28.3 pts/m², union coverage
  0.999999 of the AOI. The wider parish carries 66 tiles with no gap. This is the candidate the
  earlier draft expected to fail, and the highest density of the four.
- **Criterion 2 — CONFIRMED 2026-08-04 against the real returns.** The doubt recorded here before
  the download was sharper than the first draft admitted: the Vez valley carries pine, oak and
  riparian woodland, but the photographed Sistelo terraces are largely **open grazed pasture**,
  and a DTM under open ground demonstrates far less than a DTM under canopy. That doubt was
  **spatial**, so an aggregate could not settle it — a high AOI-wide canopy share is perfectly
  consistent with the terraces themselves being bare. Measured both ways (`docs/live-smoke.md`):
  **84.51%** of returns are above 2 m and 58.19% above 5 m over this exact AOI, and across 400
  blocks of 100 m **not one is bare**. The least wooded block in the AOI still returns 5.1% above
  2 m, the median block 88%, and 95.3% of the AOI is under real canopy. There is nowhere here for
  terraces to sit under open sky. The criterion holds on measurement, not on expectation.
  **The site therefore stands, and no re-pick is triggered.**
- **Criterion 3 — PASS, and the strongest of the four.** The Paisagem Cultural de Sistelo was
  classified as **monumento nacional by Decreto n.º 4/2018, de 15 de janeiro** — the first cultural
  landscape in Portugal to hold that classification. The terraces are not merely described in the
  literature: they are **named in the legal act itself** as a protected element. Portaria
  n.º 45/2018 (*Diário da República*, 2.ª série, n.º 13, 18 de janeiro de 2018), Artigo 1.º, alínea
  f): *"Os muros, socalcos, caminhos, calçadas e vias de acesso devem ser conservados com as
  respetivas características dimensionais, construtivas e materiais."*
  Source (read directly, primary): [Portaria n.º 45/2018, DR 2.ª série n.º 13](https://www.cmav.pt/uploads/document/file/3681/Portaria___45_2018___Paisagem_Cultural_de_Sistelo.pdf).
  Secondary: [Público, 15-01-2018](https://www.publico.pt/2018/01/15/local/noticia/classificacao-da-paisagem-de-sistelo-como-monumento-em-diario-da-republica-1799397).
  The official DGPC/SIPA record ([id 35666](http://www.monumentos.gov.pt/Site/APP_PagesUser/SIPA.aspx?id=35666)) was **not reachable** — connection refused — and the
  DGPC search returns HTTP 403 to automated fetch; neither is required, since the legal act itself
  was read.
  **Limit of this evidence, stated rather than assumed:** the perimeter of the classified landscape
  is defined in a map annexed to the Portaria, which was not obtained. What was verified is that
  the AOI is 90% inside the **Sistelo parish** (OSM administrative boundary) and centred 22 m from
  the village point. That it is inside the *classified perimeter* is inferred from that, not read.
- **Criterion 4 — PASS, with the positioning preference DECLARED AS NOT MET.** Portaria n.º 45/2018,
  Artigo 1.º alínea a), creates a **delimited** archaeological-sensitivity area: *"É criada uma área
  de sensibilidade arqueológica circundante à Igreja Paroquial de Sistelo, no lugar de Igreja,
  conforme planta anexa, onde devem ser realizadas sondagens arqueológicas de avaliação prévia nas
  ações com impacte no subsolo."* That **strengthens** criterion 4 rather than failing it: the
  sensitivity is inventoried, bounded and published, which is the opposite of the Côa condition
  below.
  The earlier draft added a positioning preference — *"the AOI is positioned away from the Igreja
  Paroquial de Sistelo, and if that proves impossible the fact is declared rather than quietly
  accepted"*. **It proved impossible, and this is the declaration.** The church sits at
  (-19916, 256166), roughly 186 m from the AOI's centre. It was measured, not assumed: of every
  2 km × 2 km block over the parish that is covered by a single sortie, the one containing the
  village amphitheatre is the **only** one on the documented terraces, and the nearest alternative
  that excludes the church is 2.2 km away, only 63% inside the parish, and carries no evidence of
  terraces at all. There is no placement that keeps the amphitheatre, a single flight, and the
  church outside.
  Three things bound what is being accepted. The sensitivity area is published and delimited, so
  its existence is not being disclosed by this piece. The act it regulates is subsoil impact, which
  a relief map is not. And **DGT already publishes a 0.5 m MDT covering this ground** — the piece
  therefore reveals no relief that the state has not already released at the same resolution.

### alto-douro-pinhao — rejected on criterion 2

- **Criterion 1 — PASS.** Nine tiles, one flight date (2024-11-22), 15.9–21.2 pts/m², coverage
  1.000. The lowest density of the four and the highest estimated void fraction (20.3%).
- **Criterion 2 — PROVISIONAL FAIL, and this is why it is not the site.** Working Douro terraces
  are planted vineyard and are **open** — no canopy. Abandoned terraces (*mortórios*) have reverted
  to Mediterranean woodland, but whether this particular 2×2 km box is mostly working vineyard or
  mostly *mortório* is unknown from text. Canopy is a requirement of the piece, not a nicety.
- **Criterion 3 — PASS.** Alto Douro Wine Region, UNESCO World Heritage inscription 1046 (2001);
  terrace typologies (*socalcos* pré-filoxera, *patamares*, *vinha ao alto*) are named in published
  descriptions. The UNESCO page itself returned HTTP 403 to automated fetch and the inscription
  details are therefore **second-hand and unverified**; they were not needed, because the
  candidate's blocker is criterion 2.
- **Criterion 4 — PASS.** No evidence found of unsurveyed archaeology specific to the Pinhão area;
  the region's known sites (Roman villae, Côa rock art) are catalogued and are tens of kilometres
  away.

### coa-valley — rejected on criterion 4

- **Criterion 1 — PASS on coverage, but the selection is refused.** Ten tiles across three flight
  dates spanning 30 days (2024-11-11, 2024-11-18, 2024-12-11), and the highest estimated void
  fraction of the four (28.3%). Processing it would require accepting a three-epoch mosaic.
- **Criterion 2 — PROVISIONAL.** Open oak woodland with scrub understorey; some pine and eucalyptus
  in abandoned parcels.
- **Criterion 3 — WEAK PASS.** The terracing itself is described only in popular and municipal
  sources, not in an official inventory or academic study.
- **Criterion 4 — FAIL. Decisive, and this candidate is excluded on it.** Archaeological survey of
  the valley is explicitly ongoing: new engravings were reported at the Fariseu site between 2020
  and the present, and published accounts describe new sites being found with successive field
  surveys. No published guidance was found on the disclosure of high-resolution remote-sensing
  products within the archaeological park — and that absence is a reason for caution, not a
  permission. This is precisely the landscape where publishing a 0.5 m relief map could be the act
  that discloses structure nobody has inventoried. Excluded.

### serra-da-estrela-manteigas — rejected on criteria 2, 3 and 4

- **Criterion 1 — PASS.** Nine tiles, one sortie of four stamps spanning 6m23s on the night of
  2025-07-04, 22.3–40.3 pts/m², coverage 1.000. This candidate is what made sortie grouping
  necessary.
- **Criterion 2 — PROVISIONAL FAIL.** The August 2022 wildfire burned this area — Copernicus EMS
  activation EMSR618 mapped Manteigas among the affected municipalities, with thousands of hectares
  of pine and cork oak lost. Canopy state in 2026 is unverified from published sources; regrowth
  three years after a stand-replacing fire is not the closed canopy this piece needs.
- **Criterion 3 — WEAK / FAIL.** The terraces are visible and remarked upon in travel writing, but
  no formal inventory or academic study of the Manteigas terraces themselves was found. Being
  *noticed* is not being *documented*: the safeguard criterion 3 provides depends on there being a
  public description to point at.
- **Criterion 4 — FAIL.** The area is archaeologically sensitive — the Estrela UNESCO Global
  Geopark documents occupation from the 4th millennium BC — and no site-level inventory for the
  Manteigas slopes was found. Sensitive *and* unsurveyed is the exact combination this criterion
  exists to exclude.

## Verdict

| Candidate | C1 coverage | C2 canopy | C3 documented | C4 no non-inventoried structure |
|---|---|---|---|---|
| **sistelo-arcos-de-valdevez** | **pass, 4 tiles, one sortie, ρ 25-28** | **PASS — measured, 0.845 above 2 m, no bare block** | **pass (strongest)** | pass, positioning preference declared unmet |
| alto-douro-pinhao | pass, ρ 16-21 | **provisional fail** | pass | pass |
| coa-valley | pass, but 3 sorties over 30 days | provisional | weak pass | **fail — excluded** |
| serra-da-estrela-manteigas | pass, ρ 22-40 | **provisional fail** | weak / fail | **fail** |

**Sistelo is the site.** It is the only candidate that passes criterion 3 in its strongest available
form, the only one whose canopy premise is not already contradicted by what the landscape is, and
the one whose data is densest. Two candidates are excluded outright on criterion 4. Alto Douro is
the runner-up and would be the fallback if criterion 2 failed on measurement — with its own criterion-2
doubt intact, which is the honest reason it is second and not first.

**What is not settled by this file.** Criterion 2 is provisional for every candidate *except the one
chosen*: it was measured for Sistelo on 2026-08-04 and passes decisively (see above and
`docs/live-smoke.md`). The three rejected candidates keep their provisional scores, because no LAZ
was ever downloaded for them — if Sistelo had failed, the fallback would have had to be measured
before being trusted, not promoted on a score of the same kind that had just been overturned.

---

## Acquisition — manual, and why

The four tiles were downloaded **by hand through the portal's browser login on 2026-08-04**, not
by a fetcher. `scripts/dgt_fetch.py` was intended and never written, because the
provider closed the automated path: `POST /token` with `grant_type=password` answers **HTTP 401
`unauthorized_client`**, and a three-request control settles which side refuses — a real password,
a junk password and a non-existent user all return the *identical* response, so the credentials are
never evaluated, while a non-existent `client_id` returns a *different* error (`invalid_client`).
The client `aai-oidc-dgt` exists and simply is not authorised for the direct grant. The operator's
credentials are fine. **A fetcher that does not exist is a fact about the provider, not a gap to be
papered over**, and building a browser-login scraper was declined deliberately: it is fragile and
buys nothing this piece is judged on.

Acceptance was the artefact, never a status code. Each file was checked with `file(1)` — all four
report *LIDAR point data records, version 1.4, SYSID AL;, Generating Software TerraScan*, header
magic `LASF` — and each size matched the catalogue's `file:size` byte for byte:

| item_id | delivered filename | bytes | catalogue `file:size` |
|---|---|---:|---:|
| `LO-179556-07-2025` | `LO-179556-07-2025_v05.laz` | 218,416,286 | 218,416,286 |
| `LO-179557-07-2025` | `LO-179557-07-2025_v05.laz` | 215,620,272 | 215,620,272 |
| `LO-180556-07-2025` | `LO-180556-07-2025_v05.laz` | 193,817,718 | 193,817,718 |
| `LO-180557-07-2025` | `LO-180557-07-2025_v05.laz` | 217,518,419 | 217,518,419 |

Total 845,372,695 bytes. Two things worth not re-deriving:

- **The delivered filename carries a `_v05` suffix the catalogue's `item_id` does not.** The files
  are stored under the bare `item_id` so the mapping back to the catalogue is mechanical, and the
  provider's own name is recorded here so the version is not lost.
- **The 64-hex segment of the download href is *not* the content hash.** Checked on all four: the
  sha256 of each file differs from the hash in its href. It is an opaque identifier, so the
  catalogue offers no free integrity check and the size match above is what stands in for one.
