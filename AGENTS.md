# Project Principles

1. Reproducibility by default: every run is re-creatable from data, config, seed, and git hash.
2. Offline-first: core workflows must not require a network connection.
3. Deterministic pipeline: ingestion, derivation, simulation, and evaluation are stable for the same inputs.
4. Traceability: inputs, parameters, outputs, and artifacts are auditable end-to-end.
5. Extensibility: new sensors, transforms, algorithms, and metrics plug in without core rewrites.
6. Transparency: algorithm outputs include human-readable signals, states, and diagnostics.
7. Safety and scope discipline: no clinical claims or medical outcome prediction.
8. Performance-aware: scale to large log sets without sacrificing correctness.
9. Testability: prefer small, verifiable units; keep a golden dataset and regression checks.
10. Data integrity: schema changes are explicit and backward-compatible when possible.

## Decision Defaults

- Prefer correctness over speed.
- Prefer clarity over cleverness.
- Prefer stable interfaces over rapid churn.
