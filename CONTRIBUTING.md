# Contributing to CareStance

Thank you for helping improve CareStance! This document gives a simple, clear workflow for interns and contributors.

## Workflow

1. Fork the repository and clone your fork
2. Create a feature branch from `main`:

```bash
git checkout -b feature/<short-description>
```

3. Make small, focused changes. Commit often with clear messages:

- Format: `type: short description`
- Examples: `feat: add unit tests for appointment model`, `fix: correct template path in dashboard`.

4. Push your branch and open a Pull Request (PR) the original repository `main` branch.

## Branch naming

- feature/<short-description>
- fix/<short-description>
- docs/<short-description>
- refactor/<short-description>

## PR Checklist

- [ ] The PR has a clear title and short description of changes
- [ ] Small, focused commits (squash if necessary on merge)
- [ ] Includes tests for any logic you change or add (unit or integration)
- [ ] All tests pass locally (`pytest -q`)
- [ ] No secrets or `.env` values committed
- [ ] Follow code style and naming conventions
- [ ] Update `README.md` or module-level docs if the behavior or setup changes

## Testing

- Run tests with `pytest -q` from the repo root.
- If you add tests, keep them deterministic and fast.

## Code Style

- Use descriptive names for functions and variables.
- Keep functions concise and single-purpose.
- Avoid one-letter variable names.

## Running linters / formatters

- Use `black` and `flake8` if configured locally. If not installed, install with:

```bash
pip install black flake8
black .
flake8
```

(If the repo later adds a pre-commit configuration, follow that.)

## Help and Communication

- For questions about tasks or mentoring, open an issue or add a comment in your PR.
- Tag your mentor or the repo owner for reviews.

Thanks — small, well-documented PRs are the fastest to review and merge.
