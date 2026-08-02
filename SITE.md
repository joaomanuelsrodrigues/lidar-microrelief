# Site selection

Criteria fixed in the design spec on 2026-07-30, **before any candidate was examined**. A site
enters only by passing all four. If none passes, the site is the blocker; the criteria do not move.

| # | Criterion | How it was checked |
|---|---|---|
| 1 | DGT coverage confirmed by a real query | `scripts/triage_candidates.py` against the live catalogue, output pasted below |
| 2 | Canopy present over the terraces | Provisional from public land cover; **confirmed after Task 9** by measuring the share of returns above 2 m |
| 3 | Terraces already publicly documented | Named source with a link, per candidate |
| 4 | No sign of non-inventoried structure | Stated explicitly, per candidate |

Criterion 3 is the one that dissolves the tension the earlier design carried: on a landscape that
is **already publicly described**, full reproducibility and prudence stop competing — publishing
the relief reveals nothing that was hidden. Documented is a *pass*, not a disappointment. Criterion
4 is its safeguard: a landscape where structure is actively being found is excluded, however
interesting, because the piece must not be the thing that discloses it.

## Status: **UNRESOLVED** as of 2026-08-02 — criterion 1 could not be measured

Criteria 2, 3 and 4 are scored below. **Criterion 1 was not measurable on 2026-08-02**: the DGT
Centro de Dados API returned HTTP 500 to every request, for every candidate, over roughly half an
hour.

This is not a finding about the candidates. A candidate that could not be reached is not a
candidate that lacks coverage, and scoring it as a failure would convert a provider outage into a
fact about the world. `scripts/triage_candidates.py` enforces that distinction mechanically: it
prints `UNMEASURED` rather than `NO COVERAGE`, and exits non-zero so an incomplete table cannot be
read as a verdict.

### Criterion 1 — evidence of the outage (verbatim)

```
$ .venv/bin/python -m ... (scripts/triage_candidates.py, first run)
sistelo-arcos-de-valdevez     UNMEASURED  CatalogueError: catalogue returned HTTP 500 ...
alto-douro-pinhao             UNMEASURED  CatalogueError: catalogue returned HTTP 500 ...
coa-valley                    UNMEASURED  CatalogueError: catalogue returned HTTP 500 ...
serra-da-estrela-manteigas    UNMEASURED  CatalogueError: catalogue returned HTTP 500 ...
```

The client was exonerated before the provider was blamed. `limit` was raised from 50 to 500 in a
recent change, so that was the first suspect; it is not the cause:

```
$ curl -s -X POST "https://cdd.dgterritorio.gov.pt/dgt-be/v1/search" \
    -H "Content-Type: application/json" \
    -d '{"bbox":[-7.55,41.18,-7.526,41.198],"collections":["LAZ"],"limit":50}'
{"status":500,"message":"Internal Server Error"}

limit=50   -> HTTP 500
limit=100  -> HTTP 500
limit=500  -> HTTP 500
```

`limit=50` is the exact request measured working on 2026-08-01, and the same bbox that returned 9
tiles then. The failure is not payload-shaped:

```
GET  /dgt-be/v1/collections      -> HTTP 500
GET  /dgt-be/v1/collections/LAZ  -> HTTP 500
POST /dgt-be/v1/search (no collections filter) -> HTTP 500
GET  /dgt-be/                    -> HTTP 200      <- the app is up
GET  /dgt-be/v1/conformance      -> HTTP 302
auth realm .well-known           -> HTTP 200      <- auth is up
```

The host and the authentication realm answer normally; the whole `/dgt-be/v1/*` catalogue surface
is erroring. Criterion 1 is re-run when it returns, and this section is replaced with the real
table.

**Forward consequence:** the fetcher session depends on the same host. If this outage persists it
blocks that session too, not only this one.

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

### sistelo-arcos-de-valdevez — bbox (-8.375, 41.930, -8.351, 41.948)

- **Criterion 1 — UNMEASURED.** See above. Note this candidate carries the highest prior risk on
  this criterion: the DGT survey covers ~90% of the territory and the gap is in the northwest.
- **Criterion 2 — PROVISIONAL PASS.** Pine and riparian woodland along the Vez, within the
  Peneda-Gerês area. Not measured; confirmed from real returns in Task 9.
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
- **Criterion 4 — PASS, with a positioning constraint.** No published statement of archaeological
  incompleteness at Sistelo was found. What the same Portaria does establish, in Artigo 1.º alínea
  a), is a **delimited** archaeological-sensitivity area: *"É criada uma área de sensibilidade
  arqueológica circundante à Igreja Paroquial de Sistelo, no lugar de Igreja, conforme planta
  anexa, onde devem ser realizadas sondagens arqueológicas de avaliação prévia nas ações com
  impacte no subsolo."* This **strengthens** the criterion rather than failing it — the sensitivity
  is inventoried, bounded and published, which is the opposite of the Côa condition below. It is
  recorded here as a constraint on where the AOI is placed: **the AOI is positioned away from the
  Igreja Paroquial de Sistelo**, and if that proves impossible the fact is declared rather than
  quietly accepted.

### alto-douro-pinhao — bbox (-7.550, 41.180, -7.526, 41.198)

- **Criterion 1 — UNMEASURED.** See above. Lowest prior risk: this is the bbox measured on
  2026-08-01 returning 9 tiles, all flown 2024-11-22, at 15.9-21.2 pts/m².
- **Criterion 2 — PROVISIONAL FAIL, and this is the candidate's weak point.** Working Douro
  terraces are planted vineyard and are **open** — no canopy. Abandoned terraces (*mortórios*) have
  reverted to Mediterranean woodland, but whether this particular 2×2 km box is mostly working
  vineyard or mostly *mortório* is unknown from text. Canopy is a requirement of the piece, not a
  nicety: a DTM under open vineyard demonstrates far less than a DTM under closed canopy.
- **Criterion 3 — PASS.** Alto Douro Wine Region, UNESCO World Heritage inscription 1046 (2001);
  terrace typologies (*socalcos* pré-filoxera, *patamares*, *vinha ao alto*) are named in published
  descriptions. The UNESCO page itself returned HTTP 403 to automated fetch and the inscription
  details are therefore **second-hand and unverified**; they were not needed, because the
  candidate's blocker is criterion 2.
- **Criterion 4 — PASS.** No evidence found of unsurveyed archaeology specific to the Pinhão area;
  the region's known sites (Roman villae, Côa rock art) are catalogued and are tens of kilometres
  away.

### coa-valley — bbox (-7.110, 41.070, -7.086, 41.088)

- **Criterion 1 — UNMEASURED.** See above.
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

### serra-da-estrela-manteigas — bbox (-7.545, 40.395, -7.521, 40.413)

- **Criterion 1 — UNMEASURED.** See above.
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

**None yet. Criterion 1 is unmeasured for all four candidates, so no candidate can pass all four,
and the pre-registered rule is that a site enters only by passing all four.** That is a statement
about the measurement, not about the sites: the stopping rule does not fire on candidates that were
never reached.

On criteria 2-4 alone, the ordering is:

| Candidate | C2 canopy | C3 documented | C4 no non-inventoried structure |
|---|---|---|---|
| sistelo-arcos-de-valdevez | provisional pass | **pass (strongest)** | pass, with a positioning constraint |
| alto-douro-pinhao | **provisional fail** | pass | pass |
| coa-valley | provisional | weak pass | **fail — excluded** |
| serra-da-estrela-manteigas | **provisional fail** | weak / fail | **fail** |

Two candidates are excluded on criterion 4. Of the two that survive it, Sistelo passes criterion 3
in its strongest available form and is the only one whose canopy premise is not already in doubt —
but it is also the one most likely to fail criterion 1, being in the northwest where the DGT survey
is incomplete. Alto Douro is the reverse: coverage is already demonstrated, canopy is the doubt.

**The two survivors are separated by exactly the measurement that is unavailable.** No pick is
recorded here until criterion 1 is measured for both.
