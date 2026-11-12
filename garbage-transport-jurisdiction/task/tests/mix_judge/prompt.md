# Semantic judge

Judge the three delivered legal documents against the supplied case materials.
Score adopted business meaning and accept professionally equivalent wording;
never require a fixed phrase or a Golden-like document length. Cite local spans
from the candidate for every dimension. Do not credit a term appearing under
the wrong property, in a rejected or hypothetical position, or without the
relation that gives it legal meaning.

- `requirement_coverage`: consider the requested filing relief and the complete
  property-specific evidence categories, dated transport events, lawful
  court-facing fallback channel, litigation-use restriction and third-party
  disclosure restriction. A focused document may be concise. Reduce credit
  when unsupported or irrelevant material makes the operative request
  ambiguous or materially burdens review; length by itself is not a defect.
- `source_fidelity`: preserve the case's known/unknown boundary. Do not treat a
  requested record as already proved, invent an issued investigation order,
  exact residence, project fact or completed transport count, or turn a private
  request into compulsory sanctions.
- `polarity_and_status`: distinguish adopted requests from alternatives,
  quotations, rejected propositions and unresolved facts. Confirm that the
  filing actually seeks reconsideration and acceptance rather than merely
  discussing those outcomes.
- `object_scope_binding`: keep Fengge Yulin and Tianguang He Huayuan records,
  dates, vehicles and requests bound to the correct property and keep the
  jurisdiction analysis bound to this transport dispute and selected court.

Use `1` only when the dimension is complete and professionally usable, `0.75`
for a minor local omission, `0.5` for a material but recoverable gap, `0.25`
for fragmentary support, and `0` when the adopted position is absent,
contradicted, fabricated or assigned to the wrong object.

Program checks own file presence, parseability and registered source-bound
propositions. Do not infer correctness from filenames, formatting or volume.
