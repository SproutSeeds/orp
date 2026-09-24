# rc.2 verification setup corrections

Claim level: **Verified** for the observed failed attempts below. These records
describe verification setup, not product readiness.

| Attempt | Result and cause | Corrective hook |
| --- | --- | --- |
| Initial isolated Python suite | FAIL: synthetic HOME removed user-site PyYAML; interpreter aliases differed | Install `requirements-test.txt` in a venv; pass `ORP_PYTHON`; rerun `npm test` |
| Initial package guard fixture | FAIL: installer guard also blocked read-only packing | Permit explicit `npm pack --dry-run --ignore-scripts`; keep installation blocked |
| Combined runner startup | FAIL: dependency package does not export package.json | Check installed dependency file; rerun combined gate |
| Initial Codex config backup check | FAIL: helper name typo, then a test used the wrong audit key | Correct helper/key; rerun Codex and rc.2 regressions |

The first final combined attempt passed all 275 Python tests but failed one Node sync fixture: parallel fake CLI reads rewrote the same JSON call log. Append-only newline records repaired that fixture. The final combined rerun passed 277 Python and 92 Node tests with zero skips. The additional Python cases cover publication guards and invalid hooks preflight.

Verification record: `results/verification/0.5.0-rc.2/VERIFICATION_RECORD.md`.
Raw local logs remain in that canonical directory and are excluded from npm.
