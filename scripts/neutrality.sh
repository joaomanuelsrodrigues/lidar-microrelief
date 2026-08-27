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
# The secrets-file rule is the repository's own: no tracked file that the STAGED root `.gitignore`
# excludes — `git show :.gitignore`, then `git ls-files -c -i --exclude-from=<that copy>` — git's
# evaluation of the copy that ships, not a regex of mine (a regex for `.env(\..+)?` let `.env-prod`,
# `.env_local` and `.env/secret` through while `.env*` ignores them) and not the working-tree file
# (an unstaged edit or an untracked nested `.gitignore` flipped the verdict; a machine's global
# excludes satisfied the precondition while the scan ignored them — measured 2026-08-27). The
# gate first requires the literal line `.env*` in that staged copy; without it, exit 2, not a
# clean tree. Negations in it (`!.env.keep`) exempt by design: an exemption belongs in `.gitignore`.
# Nested `.gitignore` files are not consulted. What is NOT here: a check of the working tree for
# untracked `.env` files — one question, one population; `.env*` is where a local secret is
# provisioned to live. (Dropped 2026-08-27 after it had been red on a sanctioned local `.env`,
# blind under any ignored directory, and machine-dependent.)
#
# Exit status: 0 clean · 1 a hit · 2 the instrument failed (git could not list the index, or it
# listed nothing — publishing zero blobs is never the question — or it holds unmerged entries,
# which `git grep --cached` skips, or git grep / cat-file did not run; no summary is printed). Every scan runs as a statement into a temporary file and its status is
# read by the caller: an `exit` inside `$(...)` ends only the subshell — measured, that version
# printed a green summary over an index it never read. stdout and stderr are kept apart: a git
# warning is an instrument note, never a hit.
#
# Silence is this gate's pass condition, and silence is also what a scan of nothing prints. So:
# the summary reports every denominator, and `--self-test` builds a temporary repository (in an
# isolated git environment: no inherited GIT_INDEX_FILE/GIT_DIR, no global config) with one
# violation of each class and requires each verdict, then a clean one and requires silence, then a
# broken instrument and requires exit 2 — running `check` exactly as production runs it, errexit
# on (a `|| true` there had exercised a different failure regime). Cite the green only beside a
# green self-test.
#
# The planted strings are assembled at run time from pieces (`%s`), never written whole in this
# file: this script is itself a tracked blob the scan reads.
set -euo pipefail
set -E; trap 'echo "neutrality: instrument failure — an unguarded command failed (line $LINENO)" >&2; exit 2' ERR
self=$(readlink -f -- "$0")   # before any cd: the self-test re-runs this script from a scratch repo
export LC_ALL=C   # byte semantics everywhere

PRIVATE_PATH='/home/[A-Za-z0-9._-]+/|C:\\+Users\\+'
EMAIL='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'

work=$(mktemp -d)
trap 'rm -r -- "$work"' EXIT

fail_instrument() {  # fail_instrument <what> <stderr-file>
  echo "neutrality: instrument failure — $1:" >&2
  cat -- "$2" >&2
  exit 2
}
fail_msg() { printf '%s\n' "$2" > "$work/err"; fail_instrument "$1" "$work/err"; }   # fail_msg <what> <message>

# run_git <what> <max-rc> <out> -- <git args…>: every git call goes through here — status
# checked against the highest status that is not a failure (0, or 1 for "no match"), stdout to
# <out>, and whatever git said on stderr echoed as an instrument note, never as a hit.
run_git() {
  local what=$1 max=$2 out=$3 rc=0; shift 4
  git "$@" > "$out" 2> "$work/err" || rc=$?
  [ "$rc" -le "$max" ] || fail_instrument "$what ($rc)" "$work/err"
  if [ -s "$work/err" ]; then { echo "neutrality: $what said:"; cat -- "$work/err"; } >&2; fi
}

run_git "git rev-parse" 0 "$work/top" -- rev-parse --show-toplevel
cd "$(<"$work/top")"

GIT_GREP_OPTS=(--cached -a -z --no-column --no-color --no-recurse-submodules)
scan_pattern() { run_git "git grep" 1 "$2" -- grep "${GIT_GREP_OPTS[@]}" -n -o -E -e "$1" -- .; }   # scan_pattern <pattern> <out>

declare -A KIND ISNUL MAILBIN UNMERGED   # type only; every value is reset at the top of check

# classify: reads $work/index (from `git ls-files -s -z`) and fills KIND[path] = text|binary for
# regular blobs, SYMLINKS (sha stage<TAB>path records) and the counters. Two git processes:
# sizes from `cat-file --batch-check`, NUL-bearing blobs from `git grep -P '\x00'`. Joins are
# exact-key lookups in associative arrays — a path is any bytes but NUL, and a per-path `grep -F`
# join read a path holding a newline as a pattern LIST (measured 2026-08-27).
classify() {
  : > "$work/shas"; : > "$work/unmerged"
  local rec path stage
  while IFS= read -r -d '' rec; do
    stage=${rec#* }; stage=${stage#* }; stage=${stage%%$'\t'*}
    # git grep --cached skips stage>0; listed once per path, not once per stage, %q-quoted
    if [ "$stage" != 0 ] && [ -z "${UNMERGED[${rec#*$'\t'}]+x}" ]; then UNMERGED[${rec#*$'\t'}]=1; printf '%q\n' "${rec#*$'\t'}" >> "$work/unmerged"; fi
    case "${rec%% *}" in
      120000) SYMLINKS+=("${rec#* }"); n_sym=$((n_sym + 1)) ;;   # "sha stage<TAB>path"
      160000) n_git=$((n_git + 1)) ;;
      *) rest=${rec#* }; printf '%s\n' "${rest%% *}" >> "$work/shas"; n_regular=$((n_regular + 1)) ;;
    esac
  done < "$work/index"
  [ ! -s "$work/unmerged" ] || fail_instrument "the index has unmerged entries, which the scan would skip" "$work/unmerged"
  run_git "git cat-file --batch-check" 0 "$work/sizes" -- cat-file --batch-check='%(objectsize)' < "$work/shas"
  run_git "git grep (NUL scan)" 1 "$work/nul" -- grep "${GIT_GREP_OPTS[@]}" -l -P -e '\x00' -- .
  while IFS= read -r -d '' path; do ISNUL[$path]=1; done < "$work/nul"
  mapfile -t sizes < "$work/sizes"
  [ "${#sizes[@]}" -eq "$n_regular" ] || fail_msg "git cat-file --batch-check" "cat-file returned ${#sizes[@]} sizes for $n_regular blobs"
  local i=0
  while IFS= read -r -d '' rec; do
    case "${rec%% *}" in 120000|160000) continue ;; esac
    path=${rec#*$'\t'}
    # a non-number is `<sha> missing` (an object git cannot read) — never a size of zero
    [[ ${sizes[$i]} =~ ^[0-9]+$ ]] || fail_msg "git cat-file --batch-check (unreadable object)" "$path: ${sizes[$i]}"
    if [ "${sizes[$i]}" -gt 0 ] && [ -z "${ISNUL[$path]+x}" ]; then KIND[$path]=text; n_text=$((n_text + 1))
    else KIND[$path]=binary; n_binary=$((n_binary + 1)); fi
    i=$((i + 1))
  done < "$work/index"
}

# judge_hits <records-file> <mode>: `path:line:match` lines for -z records. mode=all prints every
# hit; mode=text prints hits in text blobs and records the binary blobs holding one (distinct
# paths, in MAILBIN). A hit under a path the index did not list is an instrument failure.
judge_hits() {
  local path lineno match
  while IFS= read -r -d '' path && IFS= read -r -d '' lineno && IFS= read -r match; do
    [ -n "${KIND[$path]+x}" ] || fail_msg "a hit under a path the index does not list" "$path"
    if [ "$2" = all ] || [ "${KIND[$path]}" = text ]; then printf '%s:%s:%s\n' "$path" "$lineno" "$match"
    else MAILBIN[$path]=1; fi
  done < "$1"
}

# check: runs every scan in the current repository; prints verdicts; sets $hit (0/1). All state
# is reset here — the self-test runs check twice in one shell, exactly as production runs it.
check() {
  hit=0; KIND=(); ISNUL=(); MAILBIN=(); UNMERGED=(); SYMLINKS=()
  n_regular=0; n_sym=0; n_git=0; n_text=0; n_binary=0; n_mail_binary=0
  run_git "git ls-files" 0 "$work/index" -- ls-files -s -z
  [ -s "$work/index" ] || fail_msg "git listed no tracked file" "empty or unopenable index"
  # the rule must exist, in the copy that ships, before any scan prints a verdict
  run_git "git show (.gitignore)" 0 "$work/gitignore" -- show :.gitignore
  grep -qxF -- '.env*' "$work/gitignore" || fail_msg "the staged .gitignore has no '.env*' line" "the gate's secrets rule is the repository's own; add the line .env* to .gitignore and stage it"
  classify
  scan_pattern "$PRIVATE_PATH" "$work/paths"
  judge_hits "$work/paths" all > "$work/paths.txt"
  if [ -s "$work/paths.txt" ]; then echo "private path leak:"; cat -- "$work/paths.txt"; hit=1; fi
  scan_pattern "$EMAIL" "$work/mails"
  judge_hits "$work/mails" text > "$work/mails.txt"
  if [ -s "$work/mails.txt" ]; then echo "e-mail leak:"; cat -- "$work/mails.txt"; hit=1; fi
  n_mail_binary=${#MAILBIN[@]}
  : > "$work/links"
  local rec sha path
  for rec in "${SYMLINKS[@]}"; do
    sha=${rec%% *}; path=${rec#*$'\t'}
    run_git "git cat-file (symlink)" 0 "$work/target" -- cat-file blob "$sha"
    # rendered through tr, not $(cat): a NUL in a link target would be dropped with a bash warning
    if grep -qaE -- "$PRIVATE_PATH|$EMAIL" "$work/target"; then printf '%s -> %s\n' "$path" "$(tr '\0' '?' < "$work/target")" >> "$work/links"; fi
  done
  if [ -s "$work/links" ]; then echo "leak in a symlink target:"; cat -- "$work/links"; hit=1; fi
  run_git "git ls-files (ignored)" 0 "$work/ignored" -- ls-files -z -c -i --exclude-from="$work/gitignore"
  : > "$work/ignored.txt"
  # one line per path: %q only for a name holding a newline (it would span two lines); raw
  # otherwise — %q under LC_ALL=C octal-escapes every non-ASCII byte, and `é/.env` should read as such
  while IFS= read -r -d '' path; do
    if [[ $path == *$'\n'* ]]; then printf '%q\n' "$path"; else printf '%s\n' "$path"; fi
  done < "$work/ignored" > "$work/ignored.txt"
  if [ -s "$work/ignored.txt" ]; then echo "tracked though the staged .gitignore excludes it:"; cat -- "$work/ignored.txt"; hit=1; fi
}

summary() {
  echo "neutrality: $((n_regular + n_sym + n_git)) tracked ($n_regular regular, $n_sym symlink, $n_git submodule not scanned); private paths over all bytes of $n_regular; e-mails judged in $n_text text ($n_binary binary or empty, e-mail-shaped bytes in $n_mail_binary of them not judged); 0 tracked files the staged .gitignore excludes; 0 hits"
}

if [ "${1:-}" = "--self-test" ]; then
  # An isolated git: no inherited index/dir/work-tree (a pre-commit hook exports GIT_INDEX_FILE,
  # and this repository's `git add` would land in the caller's index), no user or system config.
  export HOME="$work/home"; mkdir -p "$HOME"
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  unset GIT_INDEX_FILE GIT_DIR GIT_WORK_TREE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
  # one statement per line: a failing member of an `&&` list escapes both errexit and the ERR
  # trap (measured), and a failed mkdir/cd would run the rest of this in the CALLER's repository
  mkdir "$work/repo"
  cd "$work/repo"
  [ "$PWD" = "$work/repo" ] || fail_msg "self-test" "not inside the scratch repository: $PWD"
  git init -q
  printf '.env*\n' > .gitignore
  printf 'clean\n' > clean.md
  printf 'PNG\0\0rendered on /home/%s/\n' someone > figure.png
  printf 'contact: someone%sexample.org\n' @ > notes.md
  ln -s "/home/$(printf '%s' someone)/x" link
  printf '*.md -diff\n' > .gitattributes   # would move notes.md out of `git grep -I`'s population
  # force-added files the repository's own .gitignore excludes: the regex this replaced caught
  # only the first; the last is a name carrying a newline (ANSI-C quoted: $(printf) strips it)
  PLANTED_IGNORED=(sub/.env .env-prod .env/secret $'sub/.env\n')
  mkdir -p sub .env; for f in "${PLANTED_IGNORED[@]}"; do printf 'T=1\n' > "$f"; done
  nl_path=$'q\nr.md'; printf 'contact: someone%sexample.org\n' @ > "$nl_path"   # a path holding a newline: a hit here vanished once
  # e-mail-shaped bytes inside binary blobs: counted as blobs, never judged — one plain, one under
  # a non-ASCII path git would C-quote, one holding two runs
  PLANTED_BINARY=(blob.bin "$(printf '\303\251')/blob.bin" twice.bin)
  mkdir -p "$(printf '\303\251')"
  printf 'maybe someone%sexample.org\0\n' @ > "${PLANTED_BINARY[0]}"
  printf 'x someone%sexample.org\0\n' @ > "${PLANTED_BINARY[1]}"
  printf 'two someone%sexample.org and other%sexample.com\0\n' @ @ > "${PLANTED_BINARY[2]}"
  git add .gitignore clean.md figure.png notes.md link .gitattributes "$nl_path" "${PLANTED_BINARY[@]}"
  git add -f -- "${PLANTED_IGNORED[@]}"
  check > "$work/verdicts"
  verdicts=$(<"$work/verdicts")
  expect() {  # whole-string containment: a `grep -F` here read a two-line expectation as a pattern LIST
    [[ $verdicts == *"$1"* ]] || { echo "self-test: expected '$1' NOT in verdicts:"; printf '%s\n' "$verdicts"; exit 1; }; echo "self-test: $2"; }
  expect_line() {  # a whole verdict LINE — substring containment was satisfied by a neighbouring record
    [[ $'\n'"$verdicts"$'\n' == *$'\n'"$1"$'\n'* ]] || { echo "self-test: expected line '$1' NOT in verdicts:"; printf '%s\n' "$verdicts"; exit 1; }; echo "self-test: $2"; }
  expect 'figure.png:1:/home/' 'private path behind a NUL byte caught'
  expect 'notes.md:1:someone' 'e-mail caught despite .gitattributes'
  expect 'link -> /home/' 'symlink target caught'
  expect "$nl_path:1:someone" 'e-mail in a path holding a newline caught'
  for f in "${PLANTED_IGNORED[@]}"; do expect_line "$(printf '%q' "$f")" "tracked file the staged .gitignore excludes caught: $(printf '%q' "$f")"; done
  for b in "${PLANTED_BINARY[@]}"; do
    case "$verdicts" in *"$b"*) echo "self-test: e-mail-shaped bytes in a binary blob must not be a hit ($b)"; exit 1 ;; esac
  done
  [ "$n_mail_binary" -eq "${#PLANTED_BINARY[@]}" ] || { echo "self-test: expected ${#PLANTED_BINARY[@]} e-mail-shaped binary blobs counted, got $n_mail_binary"; exit 1; }
  echo "self-test: e-mail-shaped bytes in binary blobs counted as blobs, not judged"
  git rm -q --cached figure.png notes.md link "$nl_path" "${PLANTED_BINARY[@]}" -- "${PLANTED_IGNORED[@]}"
  check > "$work/verdicts"
  [ ! -s "$work/verdicts" ] || { echo "self-test: clean planted repo still fires:"; cat -- "$work/verdicts"; exit 1; }
  echo "self-test: clean repo silent"
  rc=0; GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=grep.patternType GIT_CONFIG_VALUE_0=bogus bash "$self" > "$work/broken.out" 2> "$work/broken.err" || rc=$?
  [ "$rc" -eq 2 ] && [ ! -s "$work/broken.out" ] || { echo "self-test: a broken instrument must exit 2 with no summary (got $rc):"; cat -- "$work/broken.out" "$work/broken.err"; exit 1; }
  echo "self-test: broken instrument exits 2 with no summary"
  rc=0; GIT_INDEX_FILE="$work/no-such-index" bash "$self" > "$work/empty.out" 2> "$work/empty.err" || rc=$?
  [ "$rc" -eq 2 ] && [ ! -s "$work/empty.out" ] || { echo "self-test: an empty population must exit 2 with no summary (got $rc):"; cat -- "$work/empty.out" "$work/empty.err"; exit 1; }
  echo "self-test: empty population exits 2 with no summary"
  printf '' > .gitignore
  git add .gitignore
  rc=0; bash "$self" > "$work/norule.out" 2> "$work/norule.err" || rc=$?
  [ "$rc" -eq 2 ] && [ ! -s "$work/norule.out" ] || { echo "self-test: a staged .gitignore without .env* must exit 2 with no summary (got $rc):"; cat -- "$work/norule.out" "$work/norule.err"; exit 1; }
  echo "self-test: a staged .gitignore without .env* is an instrument failure, exit 2 with no summary"
  printf '.env*\n' > .gitignore   # the working-tree copy has the rule again; the staged one does not
  rc=0; bash "$self" > "$work/unstaged.out" 2> "$work/unstaged.err" || rc=$?
  [ "$rc" -eq 2 ] && [ ! -s "$work/unstaged.out" ] || { echo "self-test: the rule in an UNSTAGED .gitignore must not count (got $rc):"; cat -- "$work/unstaged.out" "$work/unstaged.err"; exit 1; }
  echo "self-test: the rule counts only in the staged .gitignore, not the working-tree file"
  exit 0
fi

check
[ "$hit" -eq 0 ] || exit 1
summary
