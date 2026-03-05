# ORP Run Summary `run-20260305-160605`

## Headline

- overall_result: `PASS`
- profile: `sunflower_live_compare_857`
- gates: `3 passed / 0 failed / 3 total`
- duration_ms: `4678`
- started_at_utc: `2026-03-05T16:06:05Z`
- ended_at_utc: `2026-03-05T16:06:09Z`
- config_path: `/path/to/orp.sunflower-coda.live-compare.yml`

## What This Report Shows

- Which gates ran, in what order, and with what command.
- Whether each gate passed or failed, with exit code and timing.
- Where to inspect raw evidence (`stdout` / `stderr`) for each gate.
- A deterministic input hash so teams can compare runs reliably.

## Gate Results

| Gate | Status | Exit | Duration ms | Command |
|---|---:|---:|---:|---|
| `p857_board_show` | `pass` | 0 | 1617 | `python3 scripts/problem857_ops_board.py show` |
| `p857_board_ready` | `pass` | 0 | 57 | `python3 scripts/problem857_ops_board.py ready` |
| `p857_frontier` | `pass` | 0 | 3004 | `python3 scripts/frontier_status.py --problem 857` |

## Evidence Pointers

- `p857_board_show`: stdout=`orp/artifacts/run-20260305-160605/p857_board_show.stdout.log` stderr=`orp/artifacts/run-20260305-160605/p857_board_show.stderr.log`
- `p857_board_ready`: stdout=`orp/artifacts/run-20260305-160605/p857_board_ready.stdout.log` stderr=`orp/artifacts/run-20260305-160605/p857_board_ready.stderr.log`
- `p857_frontier`: stdout=`orp/artifacts/run-20260305-160605/p857_frontier.stdout.log` stderr=`orp/artifacts/run-20260305-160605/p857_frontier.stderr.log`

## Reproducibility

- deterministic_input_hash: `sha256:d7ff4ca92c3abc93612c6cff9f080cef8b336f5f81aab0ca6125551e777a0c10`
- rerun with the same profile/config and compare this hash + gate outputs.
