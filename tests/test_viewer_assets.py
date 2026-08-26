"""The viewer's PNGs are the page a stranger opens; 18 MB for one is a page that never loads."""

from pathlib import Path

from PIL import Image

VIEWER = Path(__file__).resolve().parents[1] / "docs" / "viewer"
CAP_BYTES = 5_000_000


def test_each_viewer_png_is_under_the_cap_and_full_resolution() -> None:
    for name in ("mdt", "mds", "chm", "basis"):
        p = VIEWER / f"{name}.png"
        assert p.stat().st_size <= CAP_BYTES, (name, p.stat().st_size)
        with Image.open(p) as im:
            assert im.size == (3960, 3960), (name, im.size)


def test_the_viewer_page_and_record_moved_with_the_pngs() -> None:
    assert (VIEWER / "index.html").exists()
    assert (VIEWER / "provenance.json").exists()
