# Security Policy

## Supported Versions

Use the latest `main` branch release. Older snapshots in `tests` may include unfinished work.

## Reporting a Vulnerability

If you find a security issue, please do not open a public issue with raw reproduction steps, secrets, or exploit details.

Instead:
- Email the maintainer with a short summary and a private repro channel if available.
- If email is unavailable, open a minimal issue with enough detail to reproduce, but redact:
  - API keys, tokens, client secrets, passwords
  - Personal account identifiers
  - Full memory dumps or injected payloads

## Project Safety Model

D3OA is designed around a read-only, no-injection overlay model:
- no game memory reads or writes
- no DLL injection or API hooking in-process
- no modification of Diablo III files or network traffic

Reports suggesting otherwise are treated as high severity.

## Sensitive Patterns to Redact

When filing docs, config samples, or logs:
- replace real tokens with `[REDACTED]`
- replace real BattleTags with `YourTag#1234`
- keep sample JSON focused on structure, not live credentials
