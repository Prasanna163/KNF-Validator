# KNF Atlas Validator

Surface-level validator package for Atlas submissions.

## Layout

- `validator/` : Python package (`validator.*`)
- `tests/` : validator tests
- `pyproject.toml` : package metadata and CLI entrypoint

## Quick Start

```powershell
cd Validator
python -m pip install -e .
knf-validate --help
```

## Run Tests

```powershell
cd Validator
python -m pytest -q
```
