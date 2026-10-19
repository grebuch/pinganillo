# Release process

Pinganillo follows [semantic versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
Fixes bump PATCH, new features bump MINOR, breaking changes bump MAJOR.

## Day to day

1. Every change starts from an issue and lives on its own branch (`fix/…`, `feat/…`, `docs/…`).
2. A pull request into `main` must pass **CI** (tests on Windows and Linux, Python 3.11–3.13, lint), **Security checks** (bandit, pip-audit), **Dependency review** and **CodeQL**.
3. User-visible changes are written under `## [Unreleased]` in `CHANGELOG.md` in the same pull request.
4. `main` is protected: no direct pushes, no force pushes, checks required.

## Cutting a release

1. **Freeze**: move the `Unreleased` notes under a new heading `## [X.Y.Z-rc.N] - date` and set the version in `pyproject.toml` and `src/pinganillo/__init__.py` to the PEP 440 form (`X.Y.ZrcN`).
2. **Release candidate**: merge, then on GitHub go to *Releases → Draft a new release*, create the tag `vX.Y.Z-rc.N` on `main`, tick *Set as a pre-release*, generate the notes and publish. The *Release* workflow checks that the tag matches the package version, builds the Windows app from that tag, smoke-tests it and attaches the zip with a SHA-256 checksum.
3. **Manual test**: open a *Release checklist* issue and test the candidate on a real Windows machine. Any failure → fix through a pull request → `rc.N+1`.
4. **Final**: when a candidate passes the whole checklist, set the version to `X.Y.Z` and rename the changelog heading in a pull request (no other changes), then publish the release `vX.Y.Z` the same way, without the pre-release tick.
5. **After**: close the milestone, open the next one, and announce.

## Security

- Secret scanning with push protection and Dependabot alerts are enabled on the repository.
- All GitHub Actions are pinned to commit SHAs; Dependabot proposes updates monthly.
- Workflows run with read-only tokens; only the release job can write, and only to create the release.
- Vulnerabilities are reported privately, see [SECURITY.md](../SECURITY.md).
