# Skill Data

Skill benchmark task packages with source materials, skills, reference deliverables, and evaluators. This document defines the standard package layout and runtime contract.

## Package Layout

```text
<task-id>/
├── README.md                 # Setup and usage
├── dataset.toml              # Package index
├── RUBRIC.md                 # Scoring criteria
├── MANIFEST.json             # File inventory and hashes
├── golden/                   # Reference deliverables
└── task/                     # Runtime task root
    ├── instruction.md        # Task requirements
    ├── task.toml             # With-skill configuration
    ├── task_no_skill.toml    # No-skill configuration
    ├── environment/
    │   ├── Dockerfile        # Image and dependencies
    │   ├── skills/           # Skills and supporting resources
    │   └── workspace/        # Original task inputs
    ├── solution/
    │   └── solve.sh          # Oracle entrypoint
    └── tests/
        ├── test.sh           # Scoring entrypoint
        └── ...               # Evaluator code and reference data
```

| Path | Purpose |
| --- | --- |
| `README.md` | Package setup, dependencies, build commands, submission paths, Oracle invocation, and scoring invocation. |
| `dataset.toml` | Package identity and paths to the runtime task, rubric, and Golden. |
| `RUBRIC.md` | Scoring criteria and strict and lenient score definitions. |
| `MANIFEST.json` | Delivered file inventory, byte sizes, and SHA-256 hashes using package-relative paths. |
| `golden/` | Reference deliverables and assets required to reproduce them. |
| `task/instruction.md` | Task requirements, required output names, and submission locations. |
| `task/task.toml` | With-skill runtime configuration. |
| `task/task_no_skill.toml` | No-skill runtime configuration. |
| `task/environment/Dockerfile` | Base image and task dependencies. |
| `task/environment/skills/` | Actor-facing skills and supporting resources. |
| `task/environment/workspace/` | Original inputs supplied to the actor. |
| `task/solution/solve.sh` | Oracle entrypoint. |
| `task/tests/test.sh` | Scoring entrypoint shared by both skill conditions. |
| `task/tests/` | Evaluator code, scoring contracts, schemas, and evaluator-only reference data. |

## Paths And Visibility

- Package paths resolve from `<task-id>/`. Paths in runtime configuration resolve from `<task-id>/task/` unless explicitly absolute.
- Golden deliverables belong in `<task-id>/golden/`. The instruction, runtime configuration, Oracle, and scorer must agree on submission filenames and locations.
- Expose only the issued workspace and applicable skills to the actor. Golden, Oracle code, tests, and judge credentials are evaluator-only.
- The no-skill condition excludes skills while retaining the same inputs, task requirements, and scorer.
- Specialized build contexts belong in `task/environment/`; evaluator tools and reference data belong in `task/tests/`. An independent verifier may use `task/environment/Dockerfile.verifier`.

## Runtime

- The package README documents the required images, dependency versions, build commands, entrypoint arguments, and output paths.
- Images must include the dependencies required by the task and its evaluator. A generic base image does not replace specialized task dependencies.
- Actor and verifier network settings are explicit and independent. Online judging requires evaluator-side API access.
- Judge endpoints, models, credentials, and writable cache locations are configured externally. General provider caches and runtime outputs stay outside the package.
- Fresh scoring supports new submissions through the configured API. A package may include only the qualified, request-bound Golden replay fixture needed to reproduce the reference score; ordinary candidate caches remain external.

## Scoring

- The instruction, inputs, skills, rubric, evaluator, and Golden describe the same task boundary.
- Every mandatory task requirement has a deterministic or evidence-based semantic check. Equivalent professional expressions are accepted without requiring Golden wording.
- The evaluator does not introduce undisclosed word counts, page counts, formula counts, or other hidden thresholds.
- Deterministic checks cover facts and computations where possible. Semantic judging requires source evidence, candidate quotations, and schema-validated responses.
- Strict scores measure substantive quality. Lenient scores use the documented completion requirements and are not derived from an arbitrary strict-score threshold.
- Golden must score `strict=1.0` and `lenient=1.0` through the actual scoring entrypoint.
- Infrastructure errors, unavailable judge services, and invalid judge responses produce a structured error or `UNMEASURED` status, distinct from a candidate score of zero.

## Package Contents

The package root is limited to the six entries shown above. `golden/` contains reference deliverables and reproduction assets only.

Delivery packages exclude `repro/`, `metrics/`, rollout trajectories, development probes, calibration iterations, repair records, audit reports, historical score receipts, general provider caches, and credentials. Required runtime tools, source data, evaluator test fixtures, and the qualified exact-Golden replay fixture remain under their designated task directories.

Every manifest entry and internal resource reference must resolve to a delivered file or a documented evaluator-provided dependency. File sizes and hashes must match the actual contents. Original source materials must not be replaced with placeholders or fabricated data.
