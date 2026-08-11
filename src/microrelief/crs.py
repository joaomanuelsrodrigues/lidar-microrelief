"""Whether the coordinates are the kind this package can do arithmetic on.

`cell`, `d_max_interp_m`, `max_window_m`, `elevation_threshold_m` and every distance in
`ground.py` are metres. Handed a geographic CRS, all of them silently become degrees: a
0.5 "m" cell becomes roughly 55 km, and the output is plausible, complete and wrong. That
is the failure this package's refusal inventory exists to make impossible, so it is refused
at the one place every metric path passes through rather than checked at each use.
"""

from __future__ import annotations

from pyproj import CRS
from pyproj.exceptions import CRSError as PyprojCRSError


class CRSError(ValueError):
    """The coordinate reference system is not one we can measure metres in."""


def require_metric_crs(epsg: int) -> None:
    """Refuse anything that is not a projected CRS with all axes in metres."""
    try:
        crs = CRS.from_epsg(epsg)
    except (PyprojCRSError, ValueError) as exc:
        raise CRSError(f"EPSG:{epsg} is not a known EPSG code; refusing to assume one") from exc

    if not crs.is_projected:
        units = sorted({axis.unit_name for axis in crs.axis_info})
        raise CRSError(
            f"EPSG:{epsg} ({crs.name}) is a geographic CRS, with axes in {', '.join(units)}. "
            f"Every threshold in this package is a length in metres; on degrees they would be "
            f"applied unchanged and the output would be plausible and wrong. Reproject to a "
            f"projected CRS with metre axes first."
        )

    units = sorted({axis.unit_name for axis in crs.axis_info})
    if units != ["metre"]:
        raise CRSError(
            f"EPSG:{epsg} ({crs.name}) has axes in {', '.join(units)}, not metres; "
            f"every threshold in this package is a length in metres"
        )
