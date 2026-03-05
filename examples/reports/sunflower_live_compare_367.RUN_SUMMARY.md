# ORP Run Summary `run-20260305-160246`

## Headline

- overall_result: `PASS`
- profile: `sunflower_live_compare_367`
- gates: `3 passed / 0 failed / 3 total`
- duration_ms: `6250`
- started_at_utc: `2026-03-05T16:02:46Z`
- ended_at_utc: `2026-03-05T16:02:52Z`
- config_path: `/path/to/orp.sunflower-coda.live-compare.yml`

## What This Report Shows

- Which gates ran, in what order, and with what command.
- Whether each gate passed or failed, with exit code and timing.
- Where to inspect raw evidence (`stdout` / `stderr`) for each gate.
- A deterministic input hash so teams can compare runs reliably.

## Gate Results

| Gate | Status | Exit | Duration ms | Command |
|---|---:|---:|---:|---|
| `p367_board_show` | `pass` | 0 | 2682 | `python3 scripts/problem367_ops_board.py show` |
| `p367_board_ready` | `pass` | 0 | 649 | `python3 scripts/problem367_ops_board.py ready --allow-no-go` |
| `p367_frontier` | `pass` | 0 | 2919 | `python3 scripts/frontier_status.py --problem 367` |

## Evidence Pointers

- `p367_board_show`: stdout=`orp/artifacts/run-20260305-160246/p367_board_show.stdout.log` stderr=`orp/artifacts/run-20260305-160246/p367_board_show.stderr.log`
- `p367_board_ready`: stdout=`orp/artifacts/run-20260305-160246/p367_board_ready.stdout.log` stderr=`orp/artifacts/run-20260305-160246/p367_board_ready.stderr.log`
- `p367_frontier`: stdout=`orp/artifacts/run-20260305-160246/p367_frontier.stdout.log` stderr=`orp/artifacts/run-20260305-160246/p367_frontier.stderr.log`

## Reproducibility

- deterministic_input_hash: `sha256:f769bde4b052f7d401c866fd28abfb9d3c9626850d96830594418d45bf2b569a`
- rerun with the same profile/config and compare this hash + gate outputs.
