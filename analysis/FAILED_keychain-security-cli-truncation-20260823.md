# Failed Path Record

## Topic

Using the macOS `security` subprocess interface to restore arbitrary-length ORP
secret values

## Summary

An RC audit exposed that the `security add-generic-password -w` subprocess path
accepted only the first 128 bytes of a 164-byte credential supplied through
standard input. That path is unsuitable for ORP secret writes because a
successful exit does not prove byte-for-byte preservation.

## What was attempted

- A pre-existing local Keychain item was unintentionally overwritten during a
  write-path test.
- Its valid companion credential was resolved without printing it and supplied
  to the `security` CLI through standard input for restoration.
- The restored value was read back and compared in memory.

## Why it failed

The subprocess write completed but the exact in-memory comparison found that a
164-byte input had been truncated to 128 bytes. Exit status alone therefore
could not establish a correct Keychain write.

## Evidence (canonical artifacts)

- `cli/orp.py`: native Security.framework Keychain read, update, add, and delete
  implementation
- `tests/test_orp_auth.py`: hosted and generic secret tests that reject
  subprocess-based credential handling
- `results/verification/orp-0.5.0-rc.1-release.md`: recovery and native
  round-trip verification summary

## What this rules out

Using the `security` subprocess interface as ORP's credential write path, even
when the secret is supplied through standard input and the process exits zero.

## What might still work (next hook)

The native Security.framework implementation now writes the exact byte buffer
through `SecItemUpdate` or `SecItemAdd`. A disposable 166-byte UTF-8 value
round-tripped exactly and was deleted, and the affected pre-existing item was
restored from its validated companion with exact equality confirmed. Keep all
secret tests stubbed from the real Keychain and retain a native long-value
round-trip in release verification.
