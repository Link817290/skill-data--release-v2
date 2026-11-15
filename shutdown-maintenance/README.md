# Shutdown Maintenance

Build a four-sheet electrical shutdown-maintenance programme from the supplied
work package, calendar, resource, handback, standby, report, and oil-analysis
constraints.

The actor image is based on `harbor-claude-code-aggregated:1.3`. Run
`task/solution/solve.sh --out <directory>` for the Oracle and
`task/tests/test.sh` for evaluation. The scorer combines deterministic schedule
checks with source-bound semantic and maintainability judges. Exact Golden
replay entries are included; unseen candidates require the configured judge API.
