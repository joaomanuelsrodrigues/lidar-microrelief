# Security policy

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting on this repository:
**Security → Report a vulnerability**. That channel is private to the maintainer until an
advisory is published, and it is the only reporting channel this project offers — there is no
security mailing address.

This is a single-maintainer project with no service behind it, so there is no response-time
commitment. What is committed to: a report is acknowledged, and if it is valid the fix and the
advisory say what the problem was, not merely that one existed.

## Supported versions

The latest release on `main` only. There is no backport branch, and older tags receive no fixes.

## What the threat model actually is

This package is a **command-line tool that reads files you point it at**. It runs no server,
opens no port, stores no credentials, and executes nothing it reads. Two surfaces are worth
naming, because they are the ones that exist:

- **A LAS/LAZ file is untrusted input.** It is parsed by `laspy`; a malicious or corrupt file
  reaching a parser bug is the most plausible way this tool is made to misbehave. The package
  refuses files it cannot stand on (no CRS, an unresolvable EPSG, non-finite coordinates,
  returns outside their declared footprint), but those are *honesty* checks, not a sandbox: they
  run after `laspy` has already read the file.
- **`select` and `precheck` make one outbound request each**, to the DGT STAC catalogue. `run`
  touches no network at all. A catalogue response is parsed as JSON and never fetched further:
  an asset `href` is recorded, not followed.

Out of scope, stated so a reporter does not spend time on them: resource exhaustion from an AOI
or a cell size you chose yourself (the only ceiling is a cell count, and that limitation is
declared in the README and in every record the tool writes), and anything requiring an attacker
to already have write access to your filesystem or your `PATH`.

## Dependencies

Dependencies are pinned in `uv.lock` and installed with `uv sync --locked`. Dependabot alerts
are enabled on this repository; a vulnerability in a dependency is handled by updating the lock
file, not by patching around it here.
