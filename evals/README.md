# Project1 Versioned Evals

Run all local eval suites:

```bash
python evals/run_evals.py
```

The runner loads versioned datasets from `evals/datasets/v0.1/` and writes a JSON report to `evals/results/`.

Suites:

- `routing`: validates task routing, confidence, clarification, and risk flags.
- `acl`: validates tenant, department, role, user, group, and clearance checks.
- `security`: validates adversarial and high-risk prompts route to clarification instead of execution.
- `tooling`: validates tool budget blocking and idempotency key stability.

