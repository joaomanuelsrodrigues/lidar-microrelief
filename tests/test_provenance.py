import json
from typing import Any

import pytest

from microrelief.grid import grid_for_bounds
from microrelief.provenance import InputRef, ProvenanceError, build_provenance


def an_input(sha: str = "a" * 64, file_name: str = "LO-248470-07-2024.laz") -> InputRef:
    return InputRef(
        "LO-248470-07-2024", file_name, sha, 21184681, 21184681, 21.18, "2024-11-22T00:00:00Z"
    )


def a_provenance(**kw: Any) -> Any:
    defaults = dict(
        grid=grid_for_bounds(48000.0, 169000.0, 48100.0, 169100.0, 0.5, 3763),
        parameters={"cell": 0.5, "max_window_m": 4.0},
        inputs=(an_input(),),
        honesty={"fraction_measured": 0.91},
        agreement={"recall_ground": 0.88, "majority_class_null": 0.79},
        attribution=(
            "Source: Direção-Geral do Território (DGT), Centro de Dados, LiDAR point clouds, "
            "licensed CC BY 4.0. Derived products (ground classification, DTM, DSM, CHM) produced "
            "by microrelief; not reviewed or endorsed by DGT."
        ),
        flight_dates=("2024-11-22T00:00:00Z",),
        uncalibrated=("max_window_m", "k_min_returns"),
        limitations=("interpolation is nearest-measured, not smoothed",),
    )
    return build_provenance(**{**defaults, **kw})


def test_the_hash_is_stable_across_runs() -> None:
    assert a_provenance().reproducibility_hash == a_provenance().reproducibility_hash


def test_the_hash_ignores_the_creation_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    import microrelief.provenance as prov_mod

    a = a_provenance()

    class FrozenClock:
        @staticmethod
        def now(tz: object = None) -> datetime:
            return datetime(2020, 1, 1, tzinfo=UTC)

    monkeypatch.setattr(prov_mod, "datetime", FrozenClock)
    b = a_provenance()

    assert json.loads(a.to_json())["created_utc"] != json.loads(b.to_json())["created_utc"]
    assert a.reproducibility_hash == b.reproducibility_hash


def test_changing_a_parameter_changes_the_hash() -> None:
    assert (
        a_provenance().reproducibility_hash
        != a_provenance(parameters={"cell": 1.0, "max_window_m": 4.0}).reproducibility_hash
    )


def test_changing_an_input_file_changes_the_hash() -> None:
    assert (
        a_provenance().reproducibility_hash
        != a_provenance(inputs=(an_input(sha="b" * 64),)).reproducibility_hash
    )


def test_changing_the_grid_changes_the_hash() -> None:
    """The grid is the biggest input of all — cell size and extent decide every published number —
    and nothing else in this record stands in for it. A digest that omitted it would survive every
    other test here, because the fixture's `parameters` happens to carry a `cell` of its own."""
    assert (
        a_provenance().reproducibility_hash
        != a_provenance(
            grid=grid_for_bounds(48000.0, 169000.0, 48100.0, 169100.0, 1.0, 3763)
        ).reproducibility_hash
    )


def test_the_hash_does_not_depend_on_the_order_tiles_were_read() -> None:
    """Two runs over the same four tiles are the same run. Selection order is an accident of the
    catalogue, so it is normalised away rather than baked into the identity of the result."""
    a, b = an_input(sha="a" * 64), an_input(sha="b" * 64)
    b = InputRef("LO-248470-08-2024", "LO-248470-08-2024.laz", "b" * 64, 1, 1, 1.0, b.flight_date)
    assert (
        a_provenance(inputs=(a, b)).reproducibility_hash
        == a_provenance(inputs=(b, a)).reproducibility_hash
    )


def test_the_hash_does_not_depend_on_the_order_parameters_were_written() -> None:
    """Same run, same hash — whichever order the caller happened to build its parameter dict in.
    Without this, the digest's canonical form is untested and a mapping's insertion order leaks
    into the identity of the result."""
    assert (
        a_provenance(parameters={"cell": 0.5, "max_window_m": 4.0}).reproducibility_hash
        == a_provenance(parameters={"max_window_m": 4.0, "cell": 0.5}).reproducibility_hash
    )


def test_the_published_record_is_canonical_whatever_order_the_caller_used() -> None:
    """The file, not just the hash. A stranger diffing two runs of the same thing should see only
    the timestamp move; without a canonical serialisation they would also see the caller's dict
    insertion order, which is an accident of our own code rather than a fact about the run."""
    a = json.loads(a_provenance(parameters={"cell": 0.5, "max_window_m": 4.0}).to_json())
    b = json.loads(a_provenance(parameters={"max_window_m": 4.0, "cell": 0.5}).to_json())
    a.pop("created_utc"), b.pop("created_utc")
    assert json.dumps(a, indent=2) == json.dumps(b, indent=2)


def test_one_sortie_publishes_one_flight_date() -> None:
    """Four tiles from one flight are one epoch. `flight_dates` reads as the set of epochs the
    product is made of, so repeating the same date once per tile would make a single-sortie AOI
    look like four of them to anyone scanning the record."""
    same_day = ("2024-11-22T00:00:00Z",) * 4
    doc = json.loads(a_provenance(flight_dates=same_day).to_json())
    assert doc["flight_dates"] == ["2024-11-22T00:00:00Z"]
    assert doc["mixed_epochs"] is False


def test_the_hash_ignores_what_the_run_measured() -> None:
    """The other half of the claim: the hash changes when an *input* changes, and only then.

    `honesty` and `agreement` are results, not inputs. Folding them in would still give a stable
    hash for a faithful re-run, so no test in the plan's block can tell the two designs apart —
    but it would destroy the hash's only use: a mismatch could then mean either "you ran something
    else" or "you got something else", and the whole point is to separate those two questions.
    """
    assert (
        a_provenance().reproducibility_hash
        == a_provenance(
            honesty={"fraction_measured": 0.42},
            agreement={"recall_ground": 0.10, "majority_class_null": 0.79},
            limitations=("something else entirely",),
        ).reproducibility_hash
    )


def test_a_local_path_is_refused_rather_than_quietly_shortened() -> None:
    """A path in a published record is a leak. Silently taking the basename would hide from the
    caller that it handed over one, and `Path(...).name` does not strip a Windows separator on
    POSIX anyway (§A5), so the check names both separators and refuses."""
    for leaked in (
        "/var/tmp/tiles/LO-248470-07-2024.laz",  # not a home path: the repo's own gate forbids one
        "data\\LO-248470-07-2024.laz",
        "",
        "..",
    ):
        with pytest.raises(ProvenanceError, match="file_name"):
            an_input(file_name=leaked)


def test_only_the_file_name_is_recorded_never_the_local_path() -> None:
    doc = json.loads(a_provenance().to_json())
    blob = json.dumps(doc)
    assert "/home/" not in blob and "\\Users\\" not in blob


def test_attribution_and_uncalibrated_thresholds_are_present() -> None:
    doc = json.loads(a_provenance().to_json())
    assert "CC BY 4.0" in doc["attribution"]
    assert "Direção-Geral do Território" in doc["attribution"]
    assert "max_window_m" in doc["uncalibrated_thresholds"]


def test_mixed_epochs_is_a_field_not_a_footnote() -> None:
    doc = json.loads(
        a_provenance(flight_dates=("2024-11-22T00:00:00Z", "2025-05-30T00:00:00Z")).to_json()
    )
    assert doc["mixed_epochs"] is True
    assert len(doc["flight_dates"]) == 2


def test_a_single_epoch_says_so() -> None:
    """The sibling of the test above: `mixed_epochs` that is always True says nothing."""
    assert json.loads(a_provenance().to_json())["mixed_epochs"] is False


def test_four_stamps_from_one_sortie_are_not_mixed_epochs() -> None:
    """The AOI this package was built for: four tiles acquired minutes apart in one pass.

    `tiles.py` already decides this question, by sortie, and refuses a selection that spans two.
    Deciding it a second time here — by counting distinct stamps — makes the two modules disagree
    about a published field, and the disagreement runs the wrong way: the record and every GeoTIFF
    tag would announce `mixed_epochs: True` for a product made of a single flight. One definition,
    not two.
    """
    one_pass = (
        "2025-03-30T11:02:14+00:00",
        "2025-03-30T11:07:48+00:00",
        "2025-03-30T11:13:05+00:00",
        "2025-03-30T11:19:31+00:00",
    )
    doc = json.loads(a_provenance(flight_dates=one_pass).to_json())
    assert doc["mixed_epochs"] is False
    assert len(doc["flight_dates"]) == 4  # the stamps are still published, one per acquisition


def test_no_flight_dates_at_all_is_not_a_claim_of_one_epoch(tmp_path: Any) -> None:
    """An offline run has no catalogue and so knows no stamps. `flight_dates: []` beside
    `mixed_epochs: false` is the denominator beside the number (§A1/s258): the reader can see the
    field is empty rather than reading `false` as a measurement that was taken."""
    doc = json.loads(a_provenance(flight_dates=()).to_json())
    assert doc["flight_dates"] == []
    assert doc["mixed_epochs"] is False


def test_the_record_reports_how_many_points_it_actually_read() -> None:
    """Denominator beside the number (§A1/s258): the catalogue's count and the count we measured
    are separate fields, so a reader can see whether the file we read is the file it described."""
    doc = json.loads(a_provenance().to_json())
    (one,) = doc["inputs"]
    assert one["point_count_catalogue"] == 21184681
    assert one["point_count_measured"] == 21184681


def test_attribution_is_supplied_by_the_caller_not_baked_into_the_package() -> None:
    """A constant naming one provider, written unconditionally into every output, is a false
    source-and-licence claim on anyone else's data. The record must say what it was told."""
    doc = json.loads(a_provenance(attribution="Source: Someone Else, licensed ODbL.").to_json())
    assert doc["attribution"] == "Source: Someone Else, licensed ODbL."
    assert "Direção-Geral do Território" not in doc["attribution"]


def test_an_empty_attribution_is_refused_rather_than_published() -> None:
    """An empty attribution field reads as 'this product has no source', which is never true."""
    with pytest.raises(ProvenanceError, match="attribution"):
        a_provenance(attribution="   ")


def test_the_package_ships_no_provider_attribution_constant() -> None:
    """The lock on the defect itself: core must not hold a string it could fall back to."""
    import microrelief.provenance as provenance_module

    assert not hasattr(provenance_module, "ATTRIBUTION")


def test_attribution_stays_out_of_the_reproducibility_hash() -> None:
    """Two runs of the same data under different attributions are the same run. If this ever
    starts failing, the hash payload grew a field and every published hash is invalidated."""
    a = a_provenance(attribution="Source: A.")
    b = a_provenance(attribution="Source: B, licensed CC BY 4.0.")
    assert a.reproducibility_hash == b.reproducibility_hash
