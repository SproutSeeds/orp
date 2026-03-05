# ORP Run Summary `run-20260305-160246`

## Headline

- overall_result: `PASS`
- profile: `sunflower_live_compare_20`
- gates: `3 passed / 0 failed / 3 total`
- duration_ms: `5817`
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
| `p20_board_show` | `pass` | 0 | 2108 | `python3 scripts/problem20_ops_board.py show` |
| `p20_board_ready` | `pass` | 0 | 65 | `python3 scripts/problem20_ops_board.py ready` |
| `p20_frontier` | `pass` | 0 | 3644 | `python3 scripts/frontier_status.py --problem 20` |

## Evidence Pointers

- `p20_board_show`: stdout=`orp/artifacts/run-20260305-160246/p20_board_show.stdout.log` stderr=`orp/artifacts/run-20260305-160246/p20_board_show.stderr.log`
- `p20_board_ready`: stdout=`orp/artifacts/run-20260305-160246/p20_board_ready.stdout.log` stderr=`orp/artifacts/run-20260305-160246/p20_board_ready.stderr.log`
- `p20_frontier`: stdout=`orp/artifacts/run-20260305-160246/p20_frontier.stdout.log` stderr=`orp/artifacts/run-20260305-160246/p20_frontier.stderr.log`

## Reproducibility

- deterministic_input_hash: `sha256:a05bdc913b54a402d49456d3285b36a9afcaecc96241de63bfa3042efc3d04b2`
- rerun with the same profile/config and compare this hash + gate outputs.
