"""The record that travels with the product.

Two properties matter: a stranger holding the same inputs can re-run and verify against this
record (it names the files, their digests, the grid and every parameter — not the acquisition
route or the exact code revision, so it is a verification anchor, not a self-contained recipe),
and the hash changes when a declared input changes — grid, parameters, input digests, package
version — and only then. Code reaches the hash only through that version, and nothing enforces
the bump; the README's "What this does not support" declares this openly. The creation
timestamp is recorded and
deliberately excluded from the hash, so re-running is verifiable rather than merely plausible. So
are the run's own results: a hash that folded in what was measured could not distinguish "you ran
something else" from "you got something else", which is the one question it exists to answer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from microrelief import __version__
from microrelief.grid import Grid
from microrelief.tiles import group_sorties


class ProvenanceError(ValueError):
    """The record we were asked to build is not one we are willing to publish."""


@dataclass(frozen=True)
class InputRef:
    item_id: str
    file_name: str  # basename only: a local path in a published record is a leak, not provenance
    sha256: str
    # `None` when no catalogue entry was supplied, never the measured count copied across: the two
    # fields exist so a reader can see whether the file we read is the file the provider described,
    # and a field that cannot disagree with its sibling is decoration, not evidence.
    point_count_catalogue: int | None
    point_count_measured: int
    density_measured: float
    flight_date: str | None  # likewise absent rather than a word standing in for one
    # Returns dropped before any surface was built (ASPRS noise classes). Published rather than
    # silently subtracted: `point_count_measured` stays comparable with the catalogue's figure,
    # and a reader can see how much of the delivery this product declined to stand on.
    point_count_noise_excluded: int = 0

    def __post_init__(self) -> None:
        # Refused, not quietly shortened. Taking the basename would hide from the caller that it
        # handed over a path, and `Path(...).name` leaves a Windows separator untouched on POSIX.
        if not self.file_name or self.file_name in {".", ".."}:
            raise ProvenanceError(f"file_name must name a file, got {self.file_name!r}")
        if "/" in self.file_name or "\\" in self.file_name:
            raise ProvenanceError(
                f"file_name must be a bare file name, not a path: {self.file_name!r}"
            )


@dataclass(frozen=True)
class Provenance:
    package_version: str
    created_utc: str
    grid: dict[str, float | int]
    parameters: dict[str, object]
    inputs: tuple[InputRef, ...]
    flight_dates: tuple[str, ...]
    mixed_epochs: bool
    honesty: dict[str, float]
    agreement: dict[str, float | int]
    attribution: str
    uncalibrated_thresholds: tuple[str, ...]
    known_limitations: tuple[str, ...]
    reproducibility_hash: str = field(default="")

    def to_json(self) -> str:
        # `sort_keys` is what makes the published record canonical: two runs of the same thing
        # serialise to the same bytes even if the caller built its parameter dict in a different
        # order. It is the only normaliser on this path — nothing upstream sorts.
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False)


def _canonical(payload: Mapping[str, object]) -> str:
    # Likewise the only normaliser on the hashing path: a mapping's insertion order must not
    # reach the digest. Sorting the payload again before this call would make both mechanisms
    # invisible to any single test, which is how a pair of redundant guards rots unnoticed.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_provenance(
    grid: Grid,
    parameters: Mapping[str, object],
    inputs: Sequence[InputRef],
    honesty: Mapping[str, float],
    agreement: Mapping[str, float | int],
    attribution: str,
    flight_dates: Sequence[str],
    uncalibrated: Sequence[str],
    limitations: Sequence[str],
) -> Provenance:
    # Required, and required to say something. The package cannot know whose data this is,
    # and a default naming one provider would publish a false source claim on every other.
    if not attribution.strip():
        raise ProvenanceError(
            "attribution must name the source of the data and its licence; "
            "an empty field in a published record reads as 'this product has no source'"
        )
    grid_doc: dict[str, float | int] = {
        "origin_x": grid.origin_x,
        "origin_y": grid.origin_y,
        "cell": grid.cell,
        "n_cols": grid.n_cols,
        "n_rows": grid.n_rows,
        "crs_epsg": grid.crs_epsg,
    }
    # The declared inputs and nothing else. Code is visible only through the version term —
    # an unenforced convention, declared in the README's "What this does not support".
    digest = hashlib.sha256(
        _canonical(
            {
                "package_version": __version__,
                "grid": grid_doc,
                "parameters": dict(parameters),
                "inputs": [
                    {"item_id": i.item_id, "sha256": i.sha256}
                    for i in sorted(inputs, key=lambda i: i.item_id)
                ],
            }
        ).encode("utf-8")
    ).hexdigest()

    return Provenance(
        package_version=__version__,
        created_utc=datetime.now(UTC).isoformat(),
        grid=grid_doc,
        parameters=dict(parameters),
        inputs=tuple(sorted(inputs, key=lambda i: i.item_id)),
        flight_dates=tuple(sorted(set(flight_dates))),
        # Sorties, not distinct stamps. The catalogue stamps each tile with the moment it was
        # acquired, so one pass over four tiles arrives as four stamps minutes apart; counting
        # those would publish `mixed_epochs: True` for a single-flight product. `tiles.py` already
        # answers this question when it selects, and it has to be answered the same way here —
        # one definition, not two that can drift.
        mixed_epochs=len(group_sorties(flight_dates)) > 1,
        honesty=dict(honesty),
        agreement=dict(agreement),
        attribution=attribution,
        uncalibrated_thresholds=tuple(sorted(uncalibrated)),
        known_limitations=tuple(limitations),
        reproducibility_hash=digest,
    )
