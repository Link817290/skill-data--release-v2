# Patent claim-version triage

Counsel needs an evidence-limited technical triage of a USB charging patent. A legacy analysis used the published application, but the issued patent retained several claim numbers while changing what those claims require. The supplied packet also contains technical records for several potential comparison targets.

Prepare an English-language JSON deliverable at `/workspace/claim_chart.json`. It must conform to `/workspace/analysis_contract.json` and cover its designated published and issued comparisons, printed dependency integrity, same-number scope changes, claim-family correspondence, target-specific evidence relationships, construction dependencies, and sensitivity cases. Support substantive judgments with supplied-document locators and concise reasons, and include a short `assumptions_and_scope` collection.

Treat the result as technical claim-chart triage, not an opinion on validity, enforceability, damages, doctrine of equivalents, or ultimate liability.

The packet under `/workspace` is read-only, network access is unavailable, and the only permitted factual basis is the material supplied there. No conclusion may depend on information that is not provided in the packet. The container provides `python3` and `pdftotext`, but no `python` alias.

Check what is already available before you start.
