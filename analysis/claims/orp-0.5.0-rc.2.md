# ORP 0.5.0-rc.2 implementation

Claim level: **Verified** for the local regression and installed-package checks.

Verification Record: `results/verification/0.5.0-rc.2/VERIFICATION_RECORD.md` (**PASS**). Publication, hosted production availability and stable promotion require the remaining gates in that record.

The authorized work repairs the September 23 audit findings F01-F15, validates the installed package and hosted v2 contract, then publishes rc.2 to npm next and updates GitHub. Stable promotion retains separate real-use acceptance gates.

## Canonical artifacts

Implementation: cli/, packages/, tests/, scripts/, .github/workflows/.
Verification: results/verification/0.5.0-rc.2/.

## Working state

One release worktree starts at acc75d123ee032883a48ce751e67864e8f04eaac on release/orp-v0.5.0-rc.2. The older dirty checkout and its audit packet are preserved. Source and tests in this worktree belong to the rc.2 repair bucket; generated dependencies and package archives remain ignored.

## Next hook

Run the GitHub runtime/platform matrix, publish its tested archive to npm next, and verify registry bytes and release metadata.
