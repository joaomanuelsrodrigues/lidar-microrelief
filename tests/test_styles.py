"""The QGIS styles are the door for GIS users; the basis palette must mean what the code means.

The expected colours and codes are read from the package, not typed here: a change to
`BASIS_PALETTE` or to a basis code fails this test until the style follows.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from microrelief.export import NODATA_UINT8
from microrelief.render import BASIS_PALETTE

STYLES = Path(__file__).resolve().parents[1] / "styles"
BANDS = ("mdt", "mds", "chm", "basis", "n_all", "n_ground_asprs")
CONTINUOUS = tuple(b for b in BANDS if b != "basis")
LABELS = {0: "undetermined", 1: "measured", 2: "interpolated"}


def _renderer(name: str) -> ET.Element:
    root = ET.parse(STYLES / f"{name}.qml").getroot()
    assert root.tag == "qgis", name
    renderer = root.find(".//rasterrenderer")
    assert renderer is not None, name
    return renderer


def test_every_published_band_has_a_style_on_band_one() -> None:
    for name in BANDS:
        assert _renderer(name).get("band") == "1", name


def test_the_basis_palette_says_what_the_code_says() -> None:
    entries = {
        int(e.get("value", "")): (e.get("label"), (e.get("color") or "").lower())
        for e in _renderer("basis").iter("paletteEntry")
    }
    expected = {
        code: (LABELS[code], "#" + "".join(f"{c:02x}" for c in rgb))
        for code, rgb in BASIS_PALETTE.items()
    }
    assert entries == expected
    assert NODATA_UINT8 not in entries  # NoData is the GeoTIFF's to declare, not the style's


def test_the_continuous_styles_stretch_to_the_layer() -> None:
    for name in CONTINUOUS:
        renderer = _renderer(name)
        assert renderer.get("type") == "singlebandpseudocolor", name
        limits = renderer.find("./minMaxOrigin/limits")
        assert limits is not None and limits.text == "MinMax", name
        stops = [float(i.get("value", "nan")) for i in renderer.iter("item")]
        assert len(stops) >= 3 and stops == sorted(stops), name


def test_the_tracked_styles_are_what_the_generator_writes(tmp_path: Path) -> None:
    """Edit `scripts/make_styles.py`, regenerate, commit both — never the XML by hand."""
    import runpy

    module = runpy.run_path(str(STYLES.parent / "scripts" / "make_styles.py"))
    module["main"](["make_styles.py", str(tmp_path)])
    for name in BANDS:
        assert (tmp_path / f"{name}.qml").read_bytes() == (STYLES / f"{name}.qml").read_bytes(), (
            name
        )
