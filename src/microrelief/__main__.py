"""`python -m microrelief ...` — the way in that needs no console script on PATH.

`cli.py` carries its own `if __name__ == "__main__"` guard for `python -m microrelief.cli`,
but that spelling appears in no document: the README, the skill file and the recipes all use
the console script. The form a reader reaches for when the script is not on PATH is the
package, not the module inside it, and without this file that form fails with
`No module named microrelief.__main__` — so the guard added in 0.4.1 closed a door nobody
knocks on while the documented alternative stayed shut (found in review, s293).
"""

from __future__ import annotations

from microrelief.cli import main

raise SystemExit(main())
