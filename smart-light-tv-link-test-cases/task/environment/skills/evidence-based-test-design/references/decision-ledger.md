# Decision Ledger

A requirement is a relation, not a number. Give each independently observable
requirement a working identifier with no product meaning.

| Statement role | Use in the plan |
| --- | --- |
| Product requirement | Behavior within its stated endpoint and configuration. |
| Measurement procedure | Observation method, not authority for a new product promise. |
| Exit requirement | Its stated suite/process acceptance criterion. |
| Severity example | Failure classification after evaluating the requirement. |
| Context | Hardware/version facts; capability only if explicitly supported. |
| Authored choice | Controlled stimulus or samples, identified as test design. |

Resolve authority AFTER comparing actor, endpoint, quantity, start/stop events,
configuration and statistic. Different bindings are distinct requirements.
If equal bindings conflict and the supplied hierarchy cannot resolve them, mark
a conditional or blocked verdict with both sources. Keep supported behavior
and measurement even when a release branch is unknown.

Distinguish operation start, path restoration, readiness acknowledgement and
resumed physical effect. A convenient log timestamp does not redefine a source's
timeout origin. Similarly distinguish first visible response from a settled or
complete effect when the source governs completion.

## Working JSON

The audit accepts `facts` and `checks` lists. This is solver working data, not
a required final deliverable or a replacement for the workbook. Derive all
quoted text, identities and criteria from the inputs.

Each fact contains:

```json
{
  "id": "source-entry-id",
  "source": "input-document-name",
  "location": "location-id-from-extractor",
  "quote": "exact relevant source text",
  "authority": "requirement",
  "in_scope": true,
  "resolved": true,
  "quantity": "quantity identity",
  "endpoint": "observable identity",
  "start": "source origin or baseline identity",
  "stop": "source end event or comparison identity",
  "statistic": "source statistic identity",
  "configuration": {},
  "criterion": null
}
```

Authority is `requirement`, `procedure`, `exit`, `severity`, `context` or `authored`.
For a numerical criterion use an object with `operator`, sourced numeric `value`
and `unit`. A range uses a two-value list and operator `range`. Canonical units
include `s`, `ms`, `us`, `%`, `lux`, `count` and `Hz`. For qualitative bindings,
use descriptive start/stop/statistic identities such as `not quantitative` where
appropriate. Configuration is a dictionary of relevant states.
`resolved: false` means an unconditional final verdict is unsupported.

Each check has `id`, `case_id`, `fact_id`, the same binding fields, configuration
and criterion, plus `adopted`, `conditional` and `method`. Set check fields from
the actual workbook procedure, then compare; copying a fact is not measurement
design. Qualitative checks may have `method: null`. Quantitative checks use the
measurement-contract reference. Do not conceal a wrong check by altering the
source fact to match it.

Run the audit against extracted records. It flags missing coverage, unmatched
quotes, binding disagreement and non-acceptance statements adopted as acceptance.
Equivalent time-unit conversion is accepted. A clean report establishes internal
consistency only; manually verify the interpretation of source quotes.
