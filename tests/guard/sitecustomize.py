"""Carry Python test-effect guards into CLI subprocesses."""
import os

if os.environ.get("ORP_TEST_GUARD") == "1":
    from orp_test_safety import guarded
    _orp_guard = guarded()
    _orp_guard.__enter__()
