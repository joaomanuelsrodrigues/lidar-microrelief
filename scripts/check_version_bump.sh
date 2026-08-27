#!/usr/bin/env bash
# Warn-class guard for the F-050 gap: the reproducibility hash sees code only through
# `__version__`, and nothing else enforces the bump — so a commit that changes src/ without
# moving the version would let two different codes reuse one hash. This step makes that
# visible; it does not block (Regra 13: a new enforcement gate starts as a warning until
# a zero-violation baseline exists, and this repo's history predates the rule).
#
# Declared blindness, per F-050 itself: one commit range only (a multi-commit push is
# checked as its last step unless a range is passed in), and dirty-tree runs are invisible
# to any git-based check. Declared over-reach, the other side of the same trade: a
# comment-only edit under src/ warns too (measured on real history: the 2026-08-08 wording pass
# touched only provenance.py's comments and this guard flags it). Warn-class is what makes
# both sides of that trade liveable.
set -euo pipefail

range="${1:-HEAD~1..HEAD}"
base="${range%%..*}"
if ! git rev-parse --quiet --verify "$base^{commit}" >/dev/null 2>&1; then
    echo "version-bump guard: no base commit ($base) to compare against; nothing checked"
    exit 0
fi

# Count what was scanned and say so: silence-by-empty-diff and silence-by-clean-diff must
# not look alike (a check that scanned nothing exits 0 exactly like one that found nothing).
changed=$(git diff --name-only "$range" -- 'src/*.py' | wc -l)
version_touched=$(git diff "$range" -- src/microrelief/__init__.py | grep -c '^[+-]__version__' || true)
echo "version-bump guard over $range: $changed file(s) changed under src/," \
    "__version__ lines touched: $version_touched"

if [ "$changed" -gt 0 ] && [ "$version_touched" -eq 0 ]; then
    echo "WARN: src/ changed without a __version__ bump. Two different codes would publish"
    echo "the same reproducibility_hash (F-050). Bump src/microrelief/__init__.py and"
    echo "pyproject.toml in the same commit as the change."
    exit 1
fi
echo "version-bump guard: ok"
