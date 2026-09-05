#!/usr/bin/env bash
# histscan: the neutrality gate's two patterns, over every blob of every ref — the history, not
# the index.
#
# Why this exists beside scripts/neutrality.sh. That gate reads the INDEX: the blobs git will
# publish from the current tree. Making a repository public publishes something larger — every
# commit, every ref, every blob any of them still reaches, including a file deleted three
# releases ago. A tree-scoped scan is structurally blind to exactly that, so its green says
# nothing about the flip. This scan answers the other question, and only that one.
#
# The patterns are not written here. They are READ from scripts/neutrality.sh, so the two scans
# cannot drift apart: a repository that publishes one rule and enforces another has the rule it
# enforces. If the extraction stops finding exactly one definition of each, this exits 2 rather
# than scanning with a default of its own.
#
# Declared limit: `rev-list --objects` has no NUL-delimited form, so the object list is read line
# by line, and a tracked path containing a newline is REPORTED truncated. Measured in a scratch
# repository holding exactly such a path: the blob was still scanned and its hit still judged,
# exit 1, and only the name in the report was cut short. The mechanism by which the trailing
# fragment is discarded was NOT established -- an earlier draft of this comment asserted one and
# the probe did not show it -- so only the outcome is claimed. Named rather than hardened: no
# such path exists here, and a guard without a control is not an improvement.
#
# What it reads, and what it does not. Blobs only. Commit metadata — author and committer names
# and addresses — is NOT scanned and is not this instrument's claim; `git log --format='%ae %ce'`
# is one command and belongs in the flip's own record. Trees, tags and submodule gitlinks are
# counted and not scanned.
#
# Text and binary. An e-mail-shaped hit inside compressed bytes is a coincidence, not an address,
# so a hit is JUDGED only in a text blob and LISTED, never hidden, in a binary one. "Text" is
# decided here by one rule — a blob with no NUL byte — measured by deleting NULs and comparing
# byte counts, which needs no pattern engine and no `.gitattributes`. (The scan that ran on
# 2026-09-05 mislabelled four PNGs as text; its recorded cause, that a shell pattern cannot hold
# a NUL, does not reproduce — `grep -qaP '\x00'` finds the NUL in those same blobs. The cause is
# unestablished, which is the reason this uses an instrument that needs no escape at all.)
#
# Silence is a pass here too, so every run prints its denominators and carries controls. Two run
# before the scan: each pattern must fire on a planted known-bad string and stay quiet on clean
# text. One runs during it, on every blob: the bytes read must equal the size git declares, so a
# blob the pipeline failed to read cannot pass as a blob with nothing in it -- the reading and the
# judging are checked separately. `--must-find <ERE>` adds a named pattern that has to hit at
# least once, for a run whose green is going into a record. A scan of a shallow clone would print
# a small, meaningless denominator, so a shallow repository is refused.
# `--self-test` builds a scratch repository whose tip is clean and whose HISTORY is not, and
# requires this scan to find what an index-scoped scan cannot.
#
# Exit status: 0 clean · 1 a judged hit · 2 the instrument failed or could not be trusted.
set -euo pipefail
set -E
trap 'echo "histscan: instrument failure — an unguarded command failed (line $LINENO)" >&2; exit 2' ERR
export LC_ALL=C
set -f   # no globbing on anything read out of git

self=$(readlink -f -- "$0")
here=$(cd -- "$(dirname -- "$self")" && pwd)
gate="$here/neutrality.sh"

die() { echo "histscan: instrument failure — $1" >&2; exit 2; }

# --- the patterns, read from the gate ------------------------------------------------------
read_pattern() {  # read_pattern <VARNAME>
  local name=$1 lines
  lines=$(command grep -c "^$name=" -- "$gate" || true)
  [ "$lines" = "1" ] || die "expected exactly one definition of $name in $gate, found $lines"
  local line
  line=$(command grep -m1 "^$name=" -- "$gate")
  case $line in
    "$name="\'*\') : ;;
    *) die "$name in $gate is not a single-quoted literal; refusing to interpret it" ;;
  esac
  line=${line#"$name="\'}
  printf '%s' "${line%\'}"
}

PRIVATE_PATH=$(read_pattern PRIVATE_PATH)
EMAIL=$(read_pattern EMAIL)
[ -n "$PRIVATE_PATH" ] || die "PRIVATE_PATH read as empty"
[ -n "$EMAIL" ] || die "EMAIL read as empty"

# The patterns are read, not written: prove they still mean what their names say before scanning
# 700 blobs with them. Assembled here, never written whole — this script is itself a scanned blob.
probe_private="/home/""someone""/keys"
probe_email="a""@""b.example"
printf '%s\n' "$probe_private" | command grep -qE "$PRIVATE_PATH" || die "PRIVATE_PATH does not match a private path"
printf '%s\n' "$probe_email" | command grep -qE "$EMAIL" || die "EMAIL does not match an address"
printf '%s\n' "nothing to see here" | command grep -qE "$PRIVATE_PATH" && die "PRIVATE_PATH matches clean text"
printf '%s\n' "nothing to see here" | command grep -qE "$EMAIL" && die "EMAIL matches clean text"

# --- the scan ------------------------------------------------------------------------------
scan_repo() {  # scan_repo <repo> <control-pattern>  -> writes the report to stdout, rc via $?
  local repo=$1 control=$2
  local work rc
  work=$(mktemp -d)
  rc=0

  git -C "$repo" rev-parse --git-dir >/dev/null 2>"$work/err" || die "not a git repository: $repo"
  [ "$(git -C "$repo" rev-parse --is-shallow-repository)" = "false" ] \
    || die "shallow repository: a truncated history would print a denominator that means nothing"

  git -C "$repo" -c core.quotePath=false rev-list --objects --all > "$work/objects" 2>"$work/err" \
    || die "rev-list failed: $(cat -- "$work/err")"
  git -C "$repo" for-each-ref --format='%(refname)' > "$work/refs" 2>/dev/null || true
  local n_refs n_objects
  n_refs=$(wc -l < "$work/refs")
  n_objects=$(wc -l < "$work/objects")
  [ "$n_objects" -gt 0 ] || die "no objects reachable from any ref: nothing was scanned"

  # objects -> blobs only, keeping the first path each was seen at (a blob has no path of its own)
  : > "$work/blobs"
  while read -r sha rest; do
    [ -n "$sha" ] || continue
    printf '%s\t%s\n' "$sha" "$rest"
  done < "$work/objects" > "$work/pairs"
  cut -f1 "$work/pairs" | git -C "$repo" cat-file --batch-check='%(objectname) %(objecttype) %(objectsize)' \
    > "$work/types" 2>"$work/err" || die "cat-file --batch-check failed: $(cat -- "$work/err")"

  local n_blobs=0 n_text=0 n_binary=0 n_hits=0 n_listed=0 n_control=0 n_read=0
  : > "$work/hits"
  while read -r sha type size; do
    [ "$type" = "blob" ] || continue
    n_blobs=$((n_blobs + 1))
    local path
    path=$(awk -F'\t' -v s="$sha" '$1==s{print $2; exit}' "$work/pairs")
    git -C "$repo" cat-file blob "$sha" > "$work/blob" 2>"$work/err" \
      || die "cat-file blob $sha failed: $(cat -- "$work/err")"
    local raw stripped kind
    raw=$(wc -c < "$work/blob")
    [ "$raw" = "$size" ] || die "blob $sha: read $raw bytes, git declares $size"
    n_read=$((n_read + raw))
    stripped=$(tr -d '\000' < "$work/blob" | wc -c)
    # Non-empty and no NUL byte: the gate's own rule, worded the same way. An EMPTY blob is
    # not text here -- it was, in the first version, which put this scan's denominator one out
    # of step with the gate it borrows its patterns from. One rule, two implementations, is
    # exactly what reading the patterns from that file exists to prevent.
    if [ "$raw" -gt 0 ] && [ "$raw" = "$stripped" ]; then kind=text; n_text=$((n_text + 1))
    else kind=binary; n_binary=$((n_binary + 1)); fi

    if command grep -qaE "$PRIVATE_PATH" -- "$work/blob"; then
      printf 'HIT   private-path  %s  %s  (%s)\n' "${sha:0:12}" "$path" "$kind" >> "$work/hits"
      n_hits=$((n_hits + 1))
    fi
    if command grep -qaE "$EMAIL" -- "$work/blob"; then
      if [ "$kind" = text ]; then
        printf 'HIT   e-mail        %s  %s  (text)\n' "${sha:0:12}" "$path" >> "$work/hits"
        n_hits=$((n_hits + 1))
      else
        printf 'LIST  e-mail-shaped %s  %s  (binary, not judged)\n' "${sha:0:12}" "$path" >> "$work/hits"
        n_listed=$((n_listed + 1))
      fi
    fi
    if [ -n "$control" ] && command grep -qaE "$control" -- "$work/blob"; then
      n_control=$((n_control + 1))
    fi
  done < "$work/types"

  [ "$n_blobs" -gt 0 ] || die "no blobs among $n_objects objects: nothing was scanned"
  if [ -n "$control" ] && [ "$n_control" -eq 0 ]; then
    die "the must-find control matched 0 of $n_blobs blobs: the scan read nothing it could judge"
  fi

  cat -- "$work/hits"
  printf 'histscan: %s ref(s), %s object(s), %s blob(s) scanned (%s text, %s binary or empty); ' \
    "$n_refs" "$n_objects" "$n_blobs" "$n_text" "$n_binary"
  printf '%s byte(s) read, each blob matching the size git declares; ' "$n_read"
  if [ -n "$control" ]; then printf 'must-find control matched %s blob(s); ' "$n_control"; fi
  printf '%s judged hit(s), %s listed not judged\n' "$n_hits" "$n_listed"
  [ "$n_hits" -eq 0 ] || rc=1
  rm -r -- "$work"
  return "$rc"
}

# --- self-test -------------------------------------------------------------------------------
self_test() {
  local tmp
  tmp=$(mktemp -d)
  unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_OBJECT_DIRECTORY
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  # Assembled, never written whole: this script is a tracked blob the e-mail rule scans, and
  # writing the fixture's address here would make the gate find its own bait (it did).
  local mail
  mail=$(printf '%s@%s' t example.invalid)
  export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL="$mail"
  export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL="$mail"

  local repo="$tmp/dirty"
  mkdir -p -- "$repo"
  git -C "$repo" init -q
  # The violation is assembled at run time and lives only in this scratch repository.
  printf 'a note about %s/keys\n' "/home""/someone" > "$repo/note.md"
  git -C "$repo" add -- note.md
  git -C "$repo" commit -qm "the commit that leaks"
  printf 'a note about nothing\n' > "$repo/note.md"
  git -C "$repo" add -- note.md
  git -C "$repo" commit -qm "the commit that cleans it up"

  # The property being claimed: the tip is clean, the history is not.
  if git -C "$repo" grep -qaE "$PRIVATE_PATH" -- ':(top)'; then
    die "self-test: the scratch tip is not clean; the comparison below would prove nothing"
  fi
  local out rc
  out=$(scan_repo "$repo" "note") && rc=0 || rc=$?
  printf '%s\n' "$out" | command grep -q 'HIT   private-path' \
    || die "self-test: a private path in an unreachable-from-the-tip blob was not found"
  [ "$rc" = "1" ] || die "self-test: a judged hit must exit 1, got $rc"
  echo "self-test: a clean tip over a leaking history is found, exit 1"

  local clean="$tmp/clean"
  mkdir -p -- "$clean"
  git -C "$clean" init -q
  printf 'a note about nothing at all\n' > "$clean/note.md"   # holds the must-find word
  git -C "$clean" add -- note.md
  git -C "$clean" commit -qm "clean"
  out=$(scan_repo "$clean" "note") && rc=0 || rc=$?
  [ "$rc" = "0" ] || die "self-test: a clean history must exit 0, got $rc"
  printf '%s\n' "$out" | command grep -q 'HIT' && die "self-test: a clean history reported a hit"
  echo "self-test: a clean history is silent, exit 0"

  # A control that must not be satisfiable: a scan whose must-find pattern cannot match.
  out=$(scan_repo "$clean" "zzz-this-cannot-match-zzz" 2>&1) && rc=0 || rc=$?
  [ "$rc" = "2" ] || die "self-test: a must-find control matching nothing must exit 2, got $rc"
  echo "self-test: a must-find control that matches nothing is an instrument failure, exit 2"

  rm -r -- "$tmp"
  echo "self-test: passed"
}

case "${1-}" in
  --self-test) self_test ;;
  --must-find)
    [ -n "${2-}" ] || die "--must-find needs a pattern"
    # The verdict travels as an exit code the caller reads, never through errexit: a judged hit
    # returning 1 out of a function is not an instrument failure, and the ERR trap would call it
    # one. `die` still exits 2 from inside, which is why the two are distinguishable at all.
    rc=0
    scan_repo "$(git rev-parse --show-toplevel)" "$2" || rc=$?
    exit "$rc"
    ;;
  "")
    rc=0
    scan_repo "$(git rev-parse --show-toplevel)" "" || rc=$?
    exit "$rc"
    ;;
  *) die "unknown argument: $1 (usage: histscan.sh [--self-test | --must-find <ERE>])" ;;
esac
