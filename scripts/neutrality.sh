#!/usr/bin/env bash
# The neutrality gate: no private path, no e-mail address, no .env in the tracked tree.
#
# Members are enumerated from `git ls-files` — the registry of what the repository contains —
# never from a name pattern: the previous selector `'*.py' '*.md'` left 13 tracked text files
# unscanned (CODEOWNERS, provenance.json, pyproject.toml, uv.lock, ...). `grep -I` skips binaries
# (PNG, LAZ), which is the only exclusion, and it is by content, not by name.
#
# Silence is this gate's pass condition, and silence is also what a scan of nothing prints. So:
# the scan reports its denominator, and `--self-test` plants one violation of each class in a
# temporary file and requires each to be caught. Cite the green only beside a green self-test.
#
# The planted strings are assembled at run time from pieces (`%s`), never written whole in this
# file: this script is itself a tracked file the scan reads, and a literal violation here would
# fail the gate it exists to prove. Measured on 2026-08-26 — the first version carried the
# literals, read clean while untracked, and failed the moment it entered the index.
set -euo pipefail

PRIVATE_PATH='/home/[A-Za-z0-9._-]+/|C:\\+Users\\+'
EMAIL='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'

scan() {  # scan <pattern> <label>  — reads NUL-separated paths on stdin
  local hits
  hits=$(xargs -0 -r grep -nIE -- "$1" || true)
  if [ -n "$hits" ]; then
    echo "$2"
    echo "$hits"
    return 1
  fi
  return 0
}

if [ "${1:-}" = "--self-test" ]; then
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  printf 'x = "/home/%s/secret"\n' someone > "$tmp"
  if printf '%s\0' "$tmp" | scan "$PRIVATE_PATH" 'planted:' > /dev/null; then
    echo "self-test: private path NOT caught"; exit 1
  fi
  echo "self-test: private path caught"
  printf 'contact: someone%sexample.org\n' @ > "$tmp"
  if printf '%s\0' "$tmp" | scan "$EMAIL" 'planted:' > /dev/null; then
    echo "self-test: e-mail NOT caught"; exit 1
  fi
  echo "self-test: e-mail caught"
  exit 0
fi

n=$(git ls-files | wc -l)
status=0
git ls-files -z | scan "$PRIVATE_PATH" 'private path leak:' || status=1
git ls-files -z | scan "$EMAIL" 'e-mail leak:' || status=1
if [ -f .env ]; then echo '.env is present'; status=1; fi
if [ "$status" -eq 0 ]; then echo "neutrality: scanned $n tracked files, 0 hits"; fi
exit "$status"
