#!/usr/bin/env bash
# The neutrality gate: no private path, no e-mail address, no .env file in what this repository
# publishes.
#
# The population is the INDEX — the blobs git will publish — read through git itself
# (`git grep --cached`, `git ls-files -s`, `git cat-file`), never the working tree: a tracked file
# deleted from the checkout is still scanned, a symlink is scanned by the link text git stores
# (its target's bytes are not what ships), a path is never re-quoted or split. Earlier versions
# scanned the checkout with grep and find, and five review rounds each found the next hole in
# that choice (2026-08-26/27: cwd scope · missing files · dangling symlinks · a prune keyed on an
# untracked file · a symlink target instead of its text · a path named `-n`).
#
# Two patterns, one population. Private paths are searched in every byte of every regular blob.
# E-mail addresses are searched in every byte too, and a hit is JUDGED only in a text blob: over
# compressed bytes the pattern fires by coincidence (1 hit inside a PNG, measured), so a hit in a
# binary blob is listed as not judged, never hidden. "Text" is decided HERE, by one explicit rule
# — a non-empty blob with no NUL byte anywhere — computed by this script (two git processes: sizes
# from `cat-file --batch-check`, NUL-bearing blobs from `git grep -P '\x00'`) rather than delegated
# to `git grep -I`, which obeys `.gitattributes` and would let a tracked file move a blob out of the
# population. tests/test_neutrality_gate.py derives the same rule independently, and counts the
# e-mail-shaped binary blobs itself. Symlinks are scanned by their link text; submodules (gitlinks)
# are not scanned and are counted as such.
#
# What is NOT here: a check of the working tree for untracked `.env` files. The gate answers one
# question about one population; `.gitignore`'s `.env*` is where local secrets are provisioned to
# live, and a force-added one is caught by the tracked check. (Dropped 2026-08-27 after it had
# been red on a sanctioned local `.env`, blind under any ignored directory, and machine-dependent.)
#
# Exit status: 0 clean · 1 a hit · 2 the instrument failed (git could not list the index, or it
# listed nothing — publishing zero blobs is never the question — or git grep / cat-file did not
# run; no summary is printed). Every scan runs as a statement into a temporary file and its status is
# read by the caller: an `exit` inside `$(...)` ends only the subshell — measured, that version
# printed a green summary over an index it never read. stdout and stderr are kept apart: a git
# warning is an instrument note, never a hit.
#
# Silence is this gate's pass condition, and silence is also what a scan of nothing prints. So:
# the summary reports every denominator, and `--self-test` builds a temporary repository (in an
# isolated git environment: no inherited GIT_INDEX_FILE/GIT_DIR, no global config) with one
# violation of each class and requires each verdict, then a clean one and requires silence, then a
# broken instrument and requires exit 2. Cite the green only beside a green self-test.
#
# The planted strings are assembled at run time from pieces (`%s`), never written whole in this
# file: this script is itself a tracked blob the scan reads.
set -euo pipefail
self=$(readlink -f -- "$0")   # before any cd: the self-test re-runs this script from a scratch repo
cd "$(git rev-parse --show-toplevel)"
export LC_ALL=C   # byte semantics everywhere

PRIVATE_PATH='/home/[A-Za-z0-9._-]+/|C:\\+Users\\+'
EMAIL='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
# `.env` and `.env.<anything>` as a path segment at any depth — matching .gitignore's `.env*` as
# far as secrets go — but not `.envrc` (direnv), which is not a secrets file.
ENV_FILE='(^|/)\.env(\..+)?$'

work=$(mktemp -d)
trap 'rm -r -- "$work"' EXIT

fail_instrument() {  # fail_instrument <what> <stderr-file>
  echo "neutrality: instrument failure — $1:" >&2
  cat -- "$2" >&2
  exit 2
}

# git_grep <flags> <pattern> <out>: file:line:match for every regular blob in the index, into <out>.
# Options that a user's git config could otherwise change are pinned (-n -o -E --no-column
# --no-color --no-recurse-submodules). Records are `path\0line\0match\n` (-z): a path is never
# C-quoted or split on ':' — the previous parser lost a non-ASCII or `:<digit>` path and judged a
# binary blob as text. Exit 1 = no match; anything above 1 is an instrument failure.
git_grep() {
  local rc=0
  git grep --cached -n -o -a -E -z --no-column --no-color --no-recurse-submodules -e "$1" -- . > "$2" 2> "$work/err" || rc=$?
  [ "$rc" -le 1 ] || fail_instrument "git grep ($rc)" "$work/err"
  if [ -s "$work/err" ]; then { echo "neutrality: git grep said:"; cat -- "$work/err"; } >&2; fi
}

# print_hits <records-file> [<only-if-in NUL-list>]: `path:line:match` lines from -z records.
print_hits() {
  while IFS= read -r -d '' path && IFS= read -r -d '' lineno && IFS= read -r match; do
    if [ -n "${2:-}" ] && ! grep -zqxF -- "$path" "$2"; then continue; fi
    printf '%s:%s:%s\n' "$path" "$lineno" "$match"
  done < "$1"
}

# classify: reads $work/index (from `git ls-files -s -z`, a statement whose status the caller
# read) and writes NUL-separated path lists: $work/text and $work/binary (regular blobs, by the
# explicit rule), $work/symlinks (sha<TAB>path records) and $work/gitlinks.
classify() {
  : > "$work/text"; : > "$work/binary"; : > "$work/symlinks"; : > "$work/gitlinks"; : > "$work/shas"
  while IFS= read -r -d '' rec; do
    case "${rec%% *}" in
      120000) printf '%s\0' "${rec#* }" >> "$work/symlinks" ;;   # "sha stage<TAB>path"
      160000) printf '%s\0' "${rec#*$'\t'}" >> "$work/gitlinks" ;;
      *) rest=${rec#* }; printf '%s\n' "${rest%% *}" >> "$work/shas" ;;
    esac
  done < "$work/index"
  local rc=0
  git cat-file --batch-check='%(objectsize)' < "$work/shas" > "$work/sizes" 2> "$work/err" || rc=$?
  [ "$rc" -eq 0 ] || fail_instrument "git cat-file --batch-check ($rc)" "$work/err"
  rc=0
  git grep --cached -a -l -z -P --no-recurse-submodules -e '\x00' -- . > "$work/nul" 2> "$work/err" || rc=$?
  [ "$rc" -le 1 ] || fail_instrument "git grep -P (NUL scan, $rc)" "$work/err"
  mapfile -t sizes < "$work/sizes"
  local i=0
  while IFS= read -r -d '' rec; do
    case "${rec%% *}" in 120000|160000) continue ;; esac
    local path=${rec#*$'\t'}
    if [ "${sizes[$i]}" -gt 0 ] && ! grep -zqxF -- "$path" "$work/nul"; then
      printf '%s\0' "$path" >> "$work/text"
    else
      printf '%s\0' "$path" >> "$work/binary"
    fi
    i=$((i + 1))
  done < "$work/index"
}

# check: runs every scan in the current repository; prints verdicts; sets $hit (0/1).
check() {
  hit=0
  : > "$work/err"
  local rc=0
  git ls-files -s -z > "$work/index" 2> "$work/err" || rc=$?
  [ "$rc" -eq 0 ] || fail_instrument "git ls-files ($rc)" "$work/err"
  [ -s "$work/index" ] || { echo "neutrality: instrument failure — git listed no tracked file (empty or unopenable index)" >&2; exit 2; }
  classify
  git_grep "$PRIVATE_PATH" "$work/paths"
  print_hits "$work/paths" > "$work/paths.txt"
  if [ -s "$work/paths.txt" ]; then echo "private path leak:"; cat -- "$work/paths.txt"; hit=1; fi
  git_grep "$EMAIL" "$work/mails"
  print_hits "$work/mails" "$work/text" > "$work/mails.text"
  print_hits "$work/mails" "$work/binary" > "$work/mails.binary"
  if [ -s "$work/mails.text" ]; then echo "e-mail leak:"; cat -- "$work/mails.text"; hit=1; fi
  n_mail_binary=$(wc -l < "$work/mails.binary")
  : > "$work/links"
  while IFS= read -r -d '' rec; do
    local sha=${rec%% *} path=${rec#*$'\t'} target
    target=$(git cat-file blob "$sha" 2>> "$work/err") || fail_instrument "git cat-file (symlink)" "$work/err"
    if printf '%s\n' "$target" | grep -qE -- "$PRIVATE_PATH|$EMAIL"; then printf '%s -> %s\n' "$path" "$target" >> "$work/links"; fi
  done < "$work/symlinks"
  if [ -s "$work/links" ]; then echo "leak in a symlink target:"; cat -- "$work/links"; hit=1; fi
  tr '\0' '\n' < "$work/index" | sed 's/^[^\t]*\t//' | grep -E -- "$ENV_FILE" > "$work/env" || true
  if [ -s "$work/env" ]; then echo "tracked .env file:"; cat -- "$work/env"; hit=1; fi
}

summary() {
  local n_text n_binary n_sym n_git n_regular
  n_text=$(tr -dc '\0' < "$work/text" | wc -c); n_binary=$(tr -dc '\0' < "$work/binary" | wc -c)
  n_sym=$(tr -dc '\0' < "$work/symlinks" | wc -c); n_git=$(tr -dc '\0' < "$work/gitlinks" | wc -c)
  n_regular=$((n_text + n_binary))
  echo "neutrality: $((n_regular + n_sym + n_git)) tracked ($n_regular regular, $n_sym symlink, $n_git submodule not scanned); private paths over all bytes of $n_regular; e-mails judged in $n_text text ($n_binary binary or empty, e-mail-shaped bytes in $n_mail_binary of them not judged); 0 hits"
}

if [ "${1:-}" = "--self-test" ]; then
  # An isolated git: no inherited index/dir/work-tree (a pre-commit hook exports GIT_INDEX_FILE,
  # and this repository's `git add` would land in the caller's index), no user or system config.
  export HOME="$work/home"; mkdir -p "$HOME"
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  unset GIT_INDEX_FILE GIT_DIR GIT_WORK_TREE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
  mkdir "$work/repo" && cd "$work/repo" && git init -q
  printf 'clean\n' > clean.md
  printf 'PNG\0\0rendered on /home/%s/\n' someone > figure.png
  printf 'contact: someone%sexample.org\n' @ > notes.md
  printf 'maybe someone%sexample.org\0\n' @ > blob.bin
  mkdir -p "$(printf '\303\251')" && printf 'x someone%sexample.org\0\n' @ > "$(printf '\303\251')/blob.bin"   # a non-ASCII path git would C-quote
  ln -s "/home/$(printf '%s' someone)/x" link
  printf '*.md -diff\n' > .gitattributes   # would move notes.md out of `git grep -I`'s population
  mkdir -p sub && printf 'T=1\n' > sub/.env
  git add clean.md figure.png notes.md blob.bin link .gitattributes "$(printf '\303\251')/blob.bin" && git add -f sub/.env
  check > "$work/verdicts" || true
  expect() { grep -qF -- "$1" "$work/verdicts" || { echo "self-test: expected '$1' NOT in verdicts:"; cat -- "$work/verdicts"; exit 1; }; echo "self-test: $2"; }
  expect 'figure.png:1:/home/' 'private path behind a NUL byte caught'
  expect 'notes.md:1:someone' 'e-mail caught despite .gitattributes'
  expect 'link -> /home/' 'symlink target caught'
  expect 'sub/.env' 'tracked .env at depth caught'
  if grep -qF -- 'blob.bin' "$work/verdicts"; then echo "self-test: e-mail-shaped bytes in a binary blob must not be a hit"; exit 1; fi
  [ "$n_mail_binary" -eq 2 ] || { echo "self-test: expected 2 e-mail-shaped binary blobs counted (one under a non-ASCII path), got $n_mail_binary"; exit 1; }
  echo "self-test: e-mail-shaped bytes in two binary blobs (one under a non-ASCII path) counted, not judged"
  git rm -q --cached figure.png notes.md link sub/.env blob.bin "$(printf '\303\251')/blob.bin"
  check > "$work/verdicts" || true
  [ ! -s "$work/verdicts" ] || { echo "self-test: clean planted repo still fires:"; cat -- "$work/verdicts"; exit 1; }
  echo "self-test: clean repo silent"
  rc=0; GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=grep.patternType GIT_CONFIG_VALUE_0=bogus bash "$self" > "$work/broken.out" 2> "$work/broken.err" || rc=$?
  [ "$rc" -eq 2 ] && [ ! -s "$work/broken.out" ] || { echo "self-test: a broken instrument must exit 2 with no summary (got $rc):"; cat -- "$work/broken.out" "$work/broken.err"; exit 1; }
  echo "self-test: broken instrument exits 2 with no summary"
  rc=0; GIT_INDEX_FILE="$work/no-such-index" bash "$self" > "$work/empty.out" 2> "$work/empty.err" || rc=$?
  [ "$rc" -eq 2 ] && [ ! -s "$work/empty.out" ] || { echo "self-test: an empty population must exit 2 with no summary (got $rc):"; cat -- "$work/empty.out" "$work/empty.err"; exit 1; }
  echo "self-test: empty population exits 2 with no summary"
  for name in .env.local sub/dir/.env; do
    printf '%s\n' "$name" | grep -qE -- "$ENV_FILE" || { echo "self-test: $name NOT matched"; exit 1; }
  done
  if printf '.envrc\n' | grep -qE -- "$ENV_FILE"; then echo "self-test: .envrc wrongly matched"; exit 1; fi
  echo "self-test: .env pattern matches .env.local and sub/dir/.env, not .envrc"
  exit 0
fi

check
[ "$hit" -eq 0 ] || exit 1
summary
