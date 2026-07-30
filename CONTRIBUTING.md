# Contributing

Thank you for your interest in contributing to D3OA.

## Code of Conduct

By participating, you agree to follow the project's expected behavior:
- Be respectful and constructive.
- Focus on the code and the task, not the person.
- If you spot a problem, pair it with a reproducible step or test when possible.

## Getting Started

- Use the project interpreter for all local test runs:
  - Windows: `C:\Users\CAOZUO~1\AppData\Local\Python\bin\python.exe`
- Keep changes minimal and aligned with existing `src/`, `tests/`, and `plugins/` layout.
- Do not commit secrets. If you find a credential pattern, redact it and report it.

## Branching and Commits

- Work on `main` for stable fixes, or a dedicated feature branch when needed.
- Commit messages follow the repo convention:
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `test: ...`
  - `chore: ...`

## Testing

- Run the suite with the project interpreter before opening work for review.
- Prefer adding focused tests over broad rewrites.
- If a test depends on optional packages, make it degrade cleanly.

## Documentation

- Update `README.md` when user-facing behavior changes.
- Update `docs/TECHNICAL.md` when architecture or extension points change.
- Append dated entries to `CHANGELOG.md` for notable behavior changes.

## Security and Licensing

- Do not introduce runtime access to game memory, DLL injection, or process modification.
- See `LICENSE` for terms. Use `SECURITY.md` for vulnerability reports.
