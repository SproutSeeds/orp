#!/usr/bin/env python3
"""Required Python suite: fixture isolation lives in orp_test_support."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "tests"))
suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
if result.skipped:
    print("Required suite contains skipped checks:", result.skipped, file=sys.stderr)
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
