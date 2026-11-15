# Longitudinal pharmacovigilance adjudication

This package evaluates cross-period case-version reconciliation, candidate-level version-driver census closure, selected version-history tracing, multi-view disproportionality analysis, calibrated structured ICSR causality assessment, and revision of conclusions when follow-up evidence changes. The workspace contains two relational reporting extracts, their data dictionary, two method documents, and the requested candidate and review scopes.

The required artifact is `/workspace/faers_adjudication.json`. A condition-blind scorer reports continuous strict capability and an independent lenient completion lens. Numeric and structural checks are deterministic; wording-only evidence concepts use the standard `gpt-5.6-sol` judge with a packaged Golden replay. Network access is disabled during ordinary verification.
