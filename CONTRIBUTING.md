# Contributing to Lynx

Lynx is an experimental poker research project. Contributions that make its results easier to reproduce, its observations more reliable, or its code easier to understand are welcome.

## Set up

Install [uv](https://docs.astral.sh/uv/), clone the repository, then run from its root:

```sh
uv sync --project collector --frozen --python 3.12
uv run --project collector --no-sync pytest -q collector/tests
```

The simulation and AI modules are cross-platform. Screen capture, Windows OCR and the live advisor require Windows. Some tests deliberately skip when optional research data or large value networks are absent; report the actual test summary.

## Propose a change

1. Open an issue before a substantial feature or architecture change.
2. Branch from `main` and keep each pull request focused.
3. Add a regression test for a bug fix and update affected documentation.
4. Run the relevant tests, then the full suite. Explain any failures or skips.
5. Describe the problem, resulting behavior and validation in your pull request.

Use English for issues and pull requests where possible. Existing implementation comments and much of the technical documentation are German; translations are welcome.

## Research and data

- Compare policies on paired deals and disclose seeds, opponents, sample sizes and uncertainty.
- Keep selection, training and final evaluation data separate. Do not repeatedly rerun a failed gate until it passes.
- Distinguish newly reproduced results from the historical measurements in the case study.
- Do not commit hand-history datasets, recordings, personal information, credentials or unreviewed model files. Follow [data and licensing](docs/DATEN-UND-LIZENZEN.md).
- Keep automation inside the simulator. The live interface displays advice; it must not click, place bets, hide itself or control a poker client.

## Community

Be respectful, discuss evidence and code rather than people, and avoid personal attacks or harassment. Keep bug reports reproducible and remove private data before sharing examples. Maintainers may remove abusive content or close requests outside the project's research scope.
