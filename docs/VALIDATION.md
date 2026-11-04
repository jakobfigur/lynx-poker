# Validation record

## Initial research preview — 4 November 2026

The public source snapshot was checked locally on Windows with CPython 3.12.12 and the dependencies in `collector/uv.lock`.

```sh
uv sync --project collector --frozen --python 3.12
uv run --project collector --no-sync pytest -q collector/tests
```

Result: **247 passed, 2 skipped**, in 334.37 seconds. The skipped tests require optional raw data or a value network absent from the source package. This is a software regression result, not a rerun of the historical research benchmarks.

Gitleaks found no secrets in the exact Git publication tree. An additional pattern scan inspected the serialized model payloads without loading them. These checks reduce accidental disclosure risk but do not constitute a security audit. Model file identities are recorded in [MODEL_CHECKSUMS.sha256](MODEL_CHECKSUMS.sha256).

The CI workflow runs the locked test environment and CLI help on Windows and Linux. Check its latest run for current results; the local Windows result above does not establish a passing Linux run.
