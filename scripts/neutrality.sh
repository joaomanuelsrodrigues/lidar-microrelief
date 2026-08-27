#!/usr/bin/env bash
# The neutrality gate: no private path, no e-mail address, no .env file in what this repository
# publishes.
#
# The population is the INDEX — the blobs git will publish — read through git itself
# (`git grep --cached`, `git ls-files -s`, `git cat-file`), never the working tree: a tracked file
# deleted from the checkout is still scanned, a symlink is scanned by the link text git stores
# (its target's bytes are not what ships), a path is never re-quoted or split, and nothing here
# depends on `find`, on a per-file shell, or on which files happen to be readable. Four earlier
# versions scanned the working tree and each review round found the next hole in that choice
# (2026-08-26/27: cwd scope · missing files · dangling symlinks · a `pyvenv.cfg` prune keyed on
# an untracked file · a symlink target instead of its text · a path named `-n`).
#
# Two scans with two scopes, and the summary names both. Private paths are searched in EVERY BYTE
# of every regular blob (`-a`): a PNG's text chunk or a LAZ header is exactly where a machine path
# lands unnoticed (measured: a planted path in a PNG chunk was invisible to `-I`; 0 false hits over
# the tree). E-mail addresses are searched in text blobs only (`-I`): over compressed bytes the
# pattern fires by coincidence (1 false hit inside a PNG, measured). "Text" is git's own rule — no
# NUL in the first 8000 bytes, and at least one line — applied by the same `git grep` to the scan
# and to the count, so the denominator printed is the set actually read. Symlinks are scanned by
# their link text for both patterns; submodules (gitlinks) are not scanned and are counted as such.
#
# Silence is this gate's pass condition, and silence is also what a scan of nothing prints. So:
# the summary reports every denominator, and `--self-test` builds a temporary repository with one
# violation of each class in it (a path behind a NUL byte, a symlink whose target is a home
# directory, an ignored `.env.local`, a site-packages `.env.example` under an ignored `.venv/`
# that must NOT fire) and requires each verdict. Cite the green only beside a green self-test.
#
# The planted strings are assembled at run time from pieces (`%s`), never written whole in this
# file: this script is itself a tracked blob the scan reads.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export LC_ALL=C   # byte semantics everywhere

PRIVATE_PATH='/home/[A-Za-z0-9._-]+/|C:\\+Users\\+'
EMAIL='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
# `.env` and `.env.<anything>` as a path segment at any depth — matching .gitignore's `.env*` as
# far as secrets go — but not `.envrc` (direnv), which is not a secrets file.
ENV_FILE='(^|/)\.env(\..+)?$'

report() {  # report <label> <hits> — prints them and returns 1 when there are any
  if [ -n "$2" ]; then echo "$1"; printf '%s\n' "$2"; return 1; fi
  return 0
}

grep_index() {  # grep_index <a|I> <pattern>: file:line:match over the index's regular blobs
  # No -z: git C-quotes an unusual path name, which a report can show; a NUL delimiter would be
  # dropped by the capture (bash cannot hold one — measured, twice, on 2026-08-27).
  local out rc=0
  out=$(git grep --cached -nIo -"$1" -E -e "$2" -- . 2>&1) || rc=$?
  if [ "$rc" -gt 1 ]; then echo "git grep failed ($rc): $out" >&2; exit 2; fi
  printf '%s' "$out"
}

symlink_hits() {  # every symlink in the index whose link text matches either pattern
  git ls-files -s -z | while IFS= read -r -d '' rec; do
    [ "${rec%% *}" = 120000 ] || continue
    local rest sha path target
    rest=${rec#* }; sha=${rest%% *}; path=${rec#*$'\t'}
    target=$(git cat-file blob "$sha")
    if printf '%s\n' "$target" | grep -qE -- "$PRIVATE_PATH|$EMAIL"; then printf '%s -> %s\n' "$path" "$target"; fi
  done
}

env_tracked() { git ls-files -z | grep -zE -- "$ENV_FILE" | tr '\0' '\n' || true; }
env_worktree() {  # untracked, at git's own granularity: ignored directories collapse to one entry
  { git ls-files -z -o --exclude-standard; git ls-files -z -o -i --exclude-standard --directory; } \
    | grep -zE -- "$ENV_FILE" | tr '\0' '\n' || true
}

counts() {  # sets n_tracked n_regular n_symlink n_gitlink n_text n_skipped
  n_tracked=0; n_regular=0; n_symlink=0; n_gitlink=0
  while IFS= read -r -d '' rec; do
    n_tracked=$((n_tracked + 1))
    case "${rec%% *}" in
      120000) n_symlink=$((n_symlink + 1)) ;;
      160000) n_gitlink=$((n_gitlink + 1)) ;;
      *) n_regular=$((n_regular + 1)) ;;
    esac
  done < <(git ls-files -s -z)
  # git's rule: text, with a line. `|| true`: no text file at all is exit 1, not an error (a
  # binary-only index aborted the count under pipefail — the same shape as the count it replaced).
  n_text=$({ git grep --cached -I -l -z -e '' -- . || true; } | tr -dc '\0' | wc -c)
  n_skipped=$((n_regular - n_text))
}

check() {  # runs every check in the current repository; prints verdicts; returns 1 on any hit
  local status=0
  report 'private path leak:' "$(grep_index a "$PRIVATE_PATH")" || status=1
  report 'e-mail leak:' "$(grep_index I "$EMAIL")" || status=1
  report 'leak in a symlink target:' "$(symlink_hits)" || status=1
  report 'tracked .env file:' "$(env_tracked)" || status=1
  report '.env file present in the working tree:' "$(env_worktree)" || status=1
  return "$status"
}

if [ "${1:-}" = "--self-test" ]; then
  tmp=$(mktemp -d)
  trap 'rm -r -- "$tmp"' EXIT
  cd "$tmp" && git init -q
  printf 'clean\n' > clean.md
  printf 'PNG\0\0rendered on /home/%s/\n' someone > figure.png
  printf 'contact: someone%sexample.org\n' @ > notes.md
  ln -s "/home/$(printf '%s' someone)/x" link
  printf '.venv/\n.env*\n' > .gitignore
  mkdir -p .venv/lib/pkg && printf 'T=\n' > .venv/lib/pkg/.env.example
  printf 'T=1\n' > .env.local
  git add clean.md figure.png notes.md link .gitignore
  out=$(check || true)
  for want in 'private path leak:' 'figure.png:1:/home/' 'e-mail leak:' 'notes.md:1:someone' \
              'leak in a symlink target:' 'link -> /home/' '.env file present in the working tree:' '.env.local'; do
    case "$out" in *"$want"*) ;; *) echo "self-test: expected '$want' NOT in verdicts"; printf '%s\n' "$out"; exit 1 ;; esac
  done
  case "$out" in *'.env.example'*) echo "self-test: .venv/ contents must NOT fire"; exit 1 ;; esac
  git rm -q --cached figure.png notes.md link && rm .env.local
  out=$(check || true)
  [ -z "$out" ] || { echo "self-test: clean planted repo still fires:"; printf '%s\n' "$out"; exit 1; }
  for name in .env.local sub/dir/.env; do
    printf '%s\n' "$name" | grep -qE -- "$ENV_FILE" || { echo "self-test: $name NOT matched"; exit 1; }
  done
  if printf '.envrc\n' | grep -qE -- "$ENV_FILE"; then echo "self-test: .envrc wrongly matched"; exit 1; fi
  echo "self-test: private path behind a NUL byte caught; e-mail caught; symlink target caught; .env.local caught; .venv/ contents ignored; clean repo silent; .env pattern matches .env.local and sub/dir/.env, not .envrc"
  exit 0
fi

counts
# `if check` would consume the failing status: the first draft printed the leak and exited 0.
check || exit 1
echo "neutrality: $n_tracked tracked ($n_regular regular, $n_symlink symlink, $n_gitlink submodule not scanned); private paths over all bytes of $n_regular; e-mails over $n_text text ($n_skipped binary or empty); 0 hits"
