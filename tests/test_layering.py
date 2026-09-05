"""The dependency edge points core <- providers, and only that way.

A contract over every core module rather than a test per module: 'we forgot one' is exactly
what a per-module suite cannot see (2026-07-28). Parsed from the source rather than observed at
import time, so a module that is merely never imported during the run is still checked.

The member list is derived by walking the whole package and *subtracting* the two exempt
layers, never by a naming convention over one directory level. A contract that picks its
members by convention re-creates the gap it was written to close: a core subpackage added
later would be invisible to a top-level glob, and invisible to a completeness guard that
pinned only top-level names. So the completeness test asserts a partition — every module
under `src/microrelief` is core, or the composition root, or a provider, and the exempt ones
are named here with their reason.
"""

import ast
import sys
from pathlib import Path

import pytest

from microrelief.cli import _dgt

SRC = Path(__file__).resolve().parents[1] / "src" / "microrelief"

# The composition root is the one place allowed to know about both layers: it is what wires
# a provider to the core. It is named here, not exempted silently.
#
# `__main__.py` belongs with it rather than in core: it holds no logic, it is the `python -m
# microrelief` door that calls `cli.main`, so classifying it as core would put a module that
# imports the composition root inside the layer defined by not knowing about it. Added in
# 0.4.1, and the partition below is what forced the classification instead of letting the file
# arrive unclassified.
COMPOSITION_ROOT = {"cli.py", "__main__.py"}

# The provider layer is the side of the edge that is *allowed* to hold a network client.
PROVIDER_PREFIX = "providers/"

FORBIDDEN_IN_CORE = ("requests", "microrelief.providers", "microrelief.tiles")


def _relative(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def _all_modules() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _provider_modules() -> list[Path]:
    return [p for p in _all_modules() if _relative(p).startswith(PROVIDER_PREFIX)]


def core_modules() -> list[Path]:
    found = [
        p
        for p in _all_modules()
        if _relative(p) not in COMPOSITION_ROOT and not _relative(p).startswith(PROVIDER_PREFIX)
    ]
    assert found, "no core modules found - the walk is wrong and this test proves nothing"
    return found


def imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("module", core_modules(), ids=_relative)
def test_no_core_module_imports_a_provider_or_a_network_client(module: Path) -> None:
    offenders = {
        name
        for name in imported_names(module)
        for bad in FORBIDDEN_IN_CORE
        if name == bad or name.startswith(bad + ".")
    }
    assert not offenders, (
        f"{_relative(module)} imports {sorted(offenders)}. The core is the offline layer: the "
        f"honesty layer must not need an HTTP client for one national catalogue to be imported."
    )


def test_every_module_in_the_package_is_either_covered_or_exempt_with_a_reason() -> None:
    """Guards the membership, not the imports.

    Two ways the contract above could go vacuously green over a shrinking set: a rename that
    moved core code out of the walk, and a new subdirectory that the walk reached but nobody
    classified. The partition catches both — anything not core has to be one of the two
    exemptions named at the top of this file, and the core half is pinned by name so a module
    that quietly leaves is a failure rather than a smaller set.
    """
    expected_core = {
        "__init__.py",
        "accumulate.py",
        "crs.py",
        "density.py",
        "export.py",
        "grid.py",
        "ground.py",
        "precheck.py",
        "provenance.py",
        "read.py",
        "render.py",
        "smrf.py",
        "sorties.py",
        "surfaces.py",
    }
    assert {_relative(p) for p in core_modules()} == expected_core

    exempt = COMPOSITION_ROOT | {_relative(p) for p in _provider_modules()}
    assert {_relative(p) for p in _all_modules()} == expected_core | exempt


def test_the_contract_would_catch_a_violation() -> None:
    """Positive control. Without it, a bug in `imported_names` returning an empty set would
    make every assertion above pass over nothing."""
    assert "requests" in imported_names(SRC / "providers" / "dgt" / "catalogue.py")


def test_the_composition_root_reaches_the_provider_when_the_extra_is_installed() -> None:
    """Green control for the refusal below. Without it, a red there could equally mean the
    provider is broken, and the refusal test would be agreeing with itself."""
    assert _dgt().select_tiles is not None


def test_a_missing_provider_extra_is_named_rather_than_traced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lazy import buys the core install its independence; this is what keeps that from
    surfacing as a bare ImportError from a module the reader never asked for.

    The plan this task came from waved the branch away with `# pragma: no cover - exercised by
    the packaging test`. No such test existed, and this repo measures no coverage at all, so
    the pragma would have been a claim about an instrument that does not run. A guard nothing
    discriminates is deletable without a red (2026-08-05), so it gets a test instead.
    """
    monkeypatch.setitem(sys.modules, "microrelief.providers", None)
    with pytest.raises(SystemExit, match=r"microrelief\[dgt\]"):
        _dgt()
