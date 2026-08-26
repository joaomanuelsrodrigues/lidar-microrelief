#!/usr/bin/env bash
# The neutrality gate: no private path, no e-mail address, no .env file in the tracked tree.
#
# Members are enumerated from `git ls-files` — the registry of what the repository contains —
# never from a name pattern: the previous selector `'*.py' '*.md'` left 13 tracked text files
# unscanned (CODEOWNERS, provenance.json, pyproject.toml, uv.lock, ...).
#
# Two scans with two scopes, and the summary names both. Private paths are searched in EVERY
# BYTE of every tracked file (`grep -a`): a PNG's text chunk or a LAZ header is exactly where a
# machine path lands unnoticed, and a planted path in a PNG chunk was invisible to `grep -I`
# (measured 2026-08-27; 0 false positives over the whole tree). E-mail addresses are searched in
# text files only (`grep -I`): over compressed bytes the pattern fires by coincidence (1 false hit
# inside a PNG, measured), and the count of files that scan skips is printed beside it.
#
# Silence is this gate's pass condition, and silence is also what a scan of nothing prints. So:
# the scan reports its denominators, and `--self-test` plants one violation of each class in a
# temporary file and requires each to be caught — including a path behind a NUL byte, which only
# the all-bytes scan can see — and checks the .env pattern both ways.
# Cite the green only beside a green self-test.
#
# The planted strings are assembled at run time from pieces (`%s`), never written whole in this
# file: this script is itself a tracked file the scan reads, and a literal violation here would
# fail the gate it exists to prove. Measured on 2026-08-26 — the first version carried the
# literals, read clean while untracked, and failed the moment it entered the index.
#
# The scan runs from the repository root whatever the caller's directory: `git ls-files` lists
# only paths under the current directory, and from `docs/` this script once reported 32 files
# scanned, 0 hits, exit 0 — a plausible green over a quarter of the tree (2026-08-26).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export LC_ALL=C   # byte semantics everywhere: what counts as binary must not depend on the machine

PRIVATE_PATH='/home/[A-Za-z0-9._-]+/|C:\\+Users\\+'
EMAIL='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
# `.env` and `.env.<anything>` (`.env.local`, `.env.production`) as a path segment anywhere in the
# tree — matching .gitignore's `.env*` as far as secrets go — but not `.envrc` (direnv), which is
# not a secrets file and would make the gate fail on a developer's untracked checkout for nothing.
# One pattern drives both the tracked check and the working-tree walk.
ENV_FILE='(^|/)\.env(\..+)?$'

scan() {  # scan <grep flags> <pattern> <label>  — reads NUL-separated paths on stdin
  local hits
  hits=$(xargs -0 -r grep -nH"$1"E -- "$2" | tr -d '\0' || true)   # NULs from a binary hit would be dropped by bash with a warning
  if [ -n "$hits" ]; then
    echo "$3"
    echo "$hits"
    return 1
  fi
  return 0
}

if [ "${1:-}" = "--self-test" ]; then
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  printf 'x = "/home/%s/secret"\n' someone > "$tmp"
  if printf '%s\0' "$tmp" | scan a "$PRIVATE_PATH" 'planted:' > /dev/null; then
    echo "self-test: private path NOT caught"; exit 1
  fi
  echo "self-test: private path caught"
  printf 'PNG\0\0rendered on /home/%s/\n' someone > "$tmp"
  if printf '%s\0' "$tmp" | scan a "$PRIVATE_PATH" 'planted:' > /dev/null; then
    echo "self-test: private path behind a NUL byte NOT caught"; exit 1
  fi
  echo "self-test: private path behind a NUL byte caught"
  printf 'contact: someone%sexample.org\n' @ > "$tmp"
  if printf '%s\0' "$tmp" | scan I "$EMAIL" 'planted:' > /dev/null; then
    echo "self-test: e-mail NOT caught"; exit 1
  fi
  echo "self-test: e-mail caught"
  for name in .env.local sub/dir/.env; do
    if ! printf '%s\n' "$name" | grep -qE "$ENV_FILE"; then
      echo "self-test: $name NOT matched"; exit 1
    fi
  done
  if printf '.envrc\n' | grep -qE "$ENV_FILE"; then
    echo "self-test: .envrc wrongly matched"; exit 1
  fi
  echo "self-test: .env pattern matches .env.local and sub/dir/.env, not .envrc"
  exit 0
fi

# A tracked file deleted from the working tree is read by nobody — grep's error would be swallowed
# and it would be reported as read. Refuse before counting anything.
missing=$(git ls-files -d)
if [ -n "$missing" ]; then
  echo "tracked but missing from the working tree (not scanned):"; echo "$missing"; exit 1
fi
n_tracked=$(git ls-files | wc -l)
n_skipped=$(git ls-files -z | xargs -0 -r grep -IL . | wc -l)   # binary or empty: grep -I reads nothing
n_text=$((n_tracked - n_skipped))
status=0
git ls-files -z | scan a "$PRIVATE_PATH" 'private path leak:' || status=1
git ls-files -z | scan I "$EMAIL" 'e-mail leak:' || status=1
if git ls-files | grep -qE "$ENV_FILE"; then echo "tracked .env file:"; git ls-files | grep -E "$ENV_FILE"; status=1; fi
# The working tree at any depth, skipping .git and the virtualenv, through the same pattern —
# not `ls .env .env.*` (ls exits non-zero when any ONE operand is missing, so with no `.env` a
# present `.env.local` read as absent — positive control, 2026-08-26), not a root-only glob.
present=$(find . \( -path ./.git -o -path ./.venv \) -prune -o -type f -print | grep -E "$ENV_FILE" || true)
if [ -n "$present" ]; then echo ".env file present in the working tree:"; echo "$present"; status=1; fi
if [ "$status" -eq 0 ]; then
  echo "neutrality: scanned $n_tracked tracked files for private paths (all bytes), $n_text text files for e-mails ($n_skipped binary or empty skipped), 0 hits"
fi
exit "$status"
