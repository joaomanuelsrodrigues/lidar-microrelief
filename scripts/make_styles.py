"""Write the six QGIS styles from the package's own colours, so a style cannot drift from the code.

The basis palette is `render.BASIS_PALETTE` keyed by the `density` codes; the continuous ramps
are the colormaps `render.LAYERS` names for the viewer (the counts, which the viewer does not
draw, take viridis from zero). `tests/test_styles.py` requires the tracked files to equal this
script's output byte for byte: edit here, run `python scripts/make_styles.py`, commit both.

The continuous styles carry no fixed range: `minMaxOrigin` is MinMax over the *updated canvas*,
so QGIS stretches the ramp to the values in view at render time. Measured 2026-08-26 in QGIS
3.44 headless (docs/live-smoke.md): with `WholeRaster` a loaded .qml keeps its stored 0–1 range
and the DTM renders in two colours; with `UpdatedCanvas` the same DTM renders in 1,234. NoData
is the GeoTIFF's to declare.
"""

from __future__ import annotations

import sys
from pathlib import Path

from matplotlib import colormaps

from microrelief.density import BASIS_INTERPOLATED, BASIS_MEASURED, BASIS_UNDETERMINED
from microrelief.render import BASIS_PALETTE, LAYERS

STOPS = 9  # colour stops per continuous ramp; QGIS interpolates between them (CALIBRATIONS.md)
# Channels truncate as `render.to_rgba` does (`(lut(x) * 255).astype(np.uint8)`); rounding put
# 5 of the 9 terrain stops one unit off (measured 2026-08-26). The stops are the named colormap's
# own values; the viewer PNG additionally quantises to PALETTE_LEVELS (64 for the CHM), so a
# viewer pixel can sit up to 3 (terrain) or 8 (viridis at 64) units per channel from a stop.
COUNT_BANDS = ("n_all", "n_ground_asprs")
LABELS = {
    BASIS_UNDETERMINED: "undetermined",
    BASIS_MEASURED: "measured",
    BASIS_INTERPOLATED: "interpolated",
}

HEAD = "<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
TAIL = """    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation saturation="0" grayscaleMode="0"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
"""


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{c:02x}" for c in rgb)


def _rgba(rgb: tuple[int, int, int]) -> str:
    return f"{rgb[0]},{rgb[1]},{rgb[2]},255"


def basis_qml() -> str:
    entries = "\n".join(
        f'        <paletteEntry value="{code}" color="{_hex(rgb)}" alpha="255"'
        f' label="{LABELS[code]}"/>'
        for code, rgb in sorted(BASIS_PALETTE.items())
    )
    return (
        HEAD
        + '<qgis version="3.28" styleCategories="AllStyleCategories">\n'
        + "  <pipe>\n"
        + '    <rasterrenderer type="paletted" band="1" opacity="1" alphaBand="-1"'
        ' nodataColor="">\n'
        + "      <colorPalette>\n"
        + entries
        + "\n      </colorPalette>\n"
        + "    </rasterrenderer>\n"
        + TAIL
    )


def continuous_qml(cmap: str) -> str:
    lut = colormaps[cmap]
    stops = [
        (i / (STOPS - 1), tuple(int(c * 255) for c in lut(i / (STOPS - 1))[:3]))
        for i in range(STOPS)
    ]
    items = "\n".join(
        f'          <item value="{pos:g}" color="{_hex(rgb)}" alpha="255" label="{pos:.0%}"/>'
        for pos, rgb in stops
    )
    inner = ":".join(f"{pos:g};{_rgba(rgb)}" for pos, rgb in stops[1:-1])
    first, last = stops[0][1], stops[-1][1]
    ramp = (
        '        <colorramp type="gradient" name="[source]">\n'
        '          <Option type="Map">\n'
        f'            <Option name="color1" type="QString" value="{_rgba(first)}"/>\n'
        f'            <Option name="color2" type="QString" value="{_rgba(last)}"/>\n'
        '            <Option name="discrete" type="QString" value="0"/>\n'
        '            <Option name="rampType" type="QString" value="gradient"/>\n'
        f'            <Option name="stops" type="QString" value="{inner}"/>\n'
        "          </Option>\n"
        "        </colorramp>\n"
    )
    return (
        HEAD
        + '<qgis version="3.28" styleCategories="AllStyleCategories">\n'
        + "  <pipe>\n"
        + '    <rasterrenderer type="singlebandpseudocolor" band="1" opacity="1" alphaBand="-1"'
        ' classificationMin="0" classificationMax="1">\n'
        + "      <minMaxOrigin><limits>MinMax</limits><extent>UpdatedCanvas</extent>"
        "<statAccuracy>Exact</statAccuracy></minMaxOrigin>\n"
        + "      <rastershader>\n"
        + '        <colorrampshader colorRampType="INTERPOLATED" classificationMode="1" clip="0"'
        ' minimumValue="0" maximumValue="1">\n'
        + ramp
        + items
        + "\n        </colorrampshader>\n"
        + "      </rastershader>\n"
        + "    </rasterrenderer>\n"
        + TAIL
    )


def styles() -> dict[str, str]:
    out = {"basis": basis_qml()}
    for name, cmap, _levels in LAYERS:
        out[name] = continuous_qml(cmap)
    for name in COUNT_BANDS:
        out[name] = continuous_qml("viridis")
    return out


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1] / "styles"
    target.mkdir(parents=True, exist_ok=True)
    for name, text in styles().items():
        (target / f"{name}.qml").write_text(text, encoding="utf-8")
    print(f"wrote {len(styles())} styles to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
