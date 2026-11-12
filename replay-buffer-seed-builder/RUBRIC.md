# Rubric

The machine contract `task/tests/program_judge/rubric-contract.json` is the scoring authority.
There are 25 positive items, with weights summing to 1. Each fraction is determined by
`task_judge.py` from the corrected trajectory, phase intervals and visible project context.

```text
positive_earned = sum(weight_i * fraction_i), i=P01..P25
strict = max(0, positive_earned - sum(root-cause-deduplicated deductions))
```

## Positive items

| Item | Weight | Evaluated relation | Source |
|---|---:|---|---|
| P01 | 0.00906667 | the record's phase equals the unique interval assignment for the time the record itself selects, after any justified terminal extension | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P02 | 0.00906667 | the record's phase equals the unique interval assignment for the time the record itself selects, after any justified terminal extension | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P03 | 0.08500000 | adopted residual authority is lower before contact than after contact | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P04 | 0.00906667 | the record's phase equals the unique interval assignment for the time the record itself selects, after any justified terminal extension | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P05 | 0.05666667 | one scalar routing label is adopted per record and the precontact route differs from the later manipulation route | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P06 | 0.03966667 | the compact seed includes the corrected trajectory terminal frame under the terminal phase | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P07 | 0.00906667 | phase assignments preserve absolute annotation intervals and extend only the terminal tail | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P08 | 0.00435897 | record uses the adopted representative time, qpos_dim equals the corrected array width, and qpos_mean_abs equals its corrected row mean within 0.0000005, while a locally correct alternative row earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P09 | 0.00435897 | record uses the adopted representative time, qpos_dim equals the corrected array width, and qpos_mean_abs equals its corrected row mean within 0.0000005, while a locally correct alternative row earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P10 | 0.00435897 | record uses the adopted representative time, qpos_dim equals the corrected array width, and qpos_mean_abs equals its corrected row mean within 0.0000005, while a locally correct alternative row earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P11 | 0.00435897 | record uses the adopted representative time, qpos_dim equals the corrected array width, and qpos_mean_abs equals its corrected row mean within 0.0000005, while a locally correct alternative row earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P12 | 0.00435897 | record uses the adopted representative time, qpos_dim equals the corrected array width, and qpos_mean_abs equals its corrected row mean within 0.0000005, while a locally correct alternative row earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P13 | 0.00435897 | record uses the adopted representative time, qpos_dim equals the corrected array width, and qpos_mean_abs equals its corrected row mean within 0.0000005, while a locally correct alternative row earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P14 | 0.00435897 | record uses the adopted representative time, qpos_dim equals the corrected array width, and qpos_mean_abs equals its corrected row mean within 0.0000005, while a locally correct alternative row earns one eighth for a professionally valid alternative scaffold; the terminal record also requires base_z to equal the corrected third coordinate within 0.0000005 | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P15 | 0.00435897 | record uses the adopted representative time and base_z equals its corrected third coordinate within 0.0000005, while a correct local coordinate at another time earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P16 | 0.00435897 | record uses the adopted representative time and base_z equals its corrected third coordinate within 0.0000005, while a correct local coordinate at another time earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P17 | 0.00435897 | record uses the adopted representative time and base_z equals its corrected third coordinate within 0.0000005, while a correct local coordinate at another time earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P18 | 0.00435897 | record uses the adopted representative time and base_z equals its corrected third coordinate within 0.0000005, while a correct local coordinate at another time earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P19 | 0.00435897 | record uses the adopted representative time and base_z equals its corrected third coordinate within 0.0000005, while a correct local coordinate at another time earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P20 | 0.00435902 | record uses the adopted representative time and base_z equals its corrected third coordinate within 0.0000005, while a correct local coordinate at another time earns one eighth for a professionally valid alternative scaffold | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P21 | 0.02833333 | the selected times include the episode origin | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P22 | 0.00906665 | every declared phase, including a short transition phase between coarse anchors, has at least one representative row | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P23 | 0.02833334 | the interior anchors lie on one coarse cadence, apart from at most one interior point per short phase | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P24 | 0.33000000 | every record's target components use a coherent unit normalization (`sum = 1` probability shares or `max = 1` peak-relative targets), and the dominant component follows tracking before contact, contact through closure, and lift only after stable grasp | materials/trajectory_unified.npz and materials/grasp_phase_segments.json |
| P25 | 0.33000000 | routing labels are semantically equivalent to the two consumer routes evidenced by `ppo_script.py`: precontact records feed pretraining/imitation and later manipulation records feed PPO/reinforcement-learning; both phase groups must be consistently routable | materials/ppo_script.py and submitted `use_for` values |

P01/P02/P04 test the selected record's own phase relation. P08-P14 recompute corrected
row means/dimensions (including terminal base), P15-P20 recompute base coordinates.
No private representative-time identity gate is applied. P03/P05-P07 test residual
authority, phase routing, terminal coverage and absolute annotation intervals. P21-P23
test origin, phase coverage and cadence. P24 (0.33) accepts unit-sum and
peak-relative unit normalization while separately testing phase-appropriate
dominance; P25 (0.33) is a source-bound `gpt-5.6-sol` semantic
decision over exact candidate labels and exact `ppo_script.py` evidence. It accepts
equivalent professional names without using keyword lists. Exact target constants are
not required, but their normalization and objective ordering are scored.

P24 and P25 each carry 33% because they are the two consumer-facing contracts:
the target vector must express the correct objective ordering, and the routing
label must send the record to the correct learning phase. A seed with accurate
coordinates but an inverted objective or route is operationally wrong. The
remaining 34% is distributed across phase assignment, residual authority,
terminal coverage, cadence and source-derived coordinates so local extraction
quality remains visible without allowing many small numeric checks to outweigh
either end-use contract. The 0.01 deductions address local malformed or
contradictory records and are capped per error family at 0.2; they expose repeated
data-integrity damage without erasing independently valid records. These shares
reflect downstream training impact rather than a fitted score boundary.

## Deductions

| Item | Trigger | Scale | Maximum |
|---|---|---:|---:|
| D01 | artifact is not valid nonempty JSONL | 0.01 | 0.2 |
| D02 | a JSONL line is not an object | 0.01 | 0.2 |
| D03 | t is not an integer | 0.01 | 0.2 |
| D04 | t is outside the corrected trajectory | 0.01 | 0.2 |
| D05 | two records reuse the same t | 0.01 | 0.2 |
| D06 | records are not strictly ascending by t | 0.01 | 0.2 |
| D07 | phase contradicts the bound interval | 0.01 | 0.2 |
| D08 | qpos_mean_abs contradicts corrected qpos | 0.01 | 0.2 |
| D09 | qpos_dim contradicts corrected qpos width | 0.01 | 0.2 |
| D10 | base_z contradicts the third corrected qpos coordinate | 0.01 | 0.2 |
| D11 | a record adds unsupported top level fields | 0.01 | 0.2 |
| D12 | a nested scored object has an incompatible type | 0.01 | 0.2 |
| D13 | an observation matches qpos_original while contradicting corrected qpos | 0.01 | 0.2 |
| D14 | a scored numeric field is nonfinite | 0.01 | 0.2 |
| D15 | finger residual limit is negative | 0.01 | 0.2 |
| D16 | a reward target is outside zero to one | 0.01 | 0.2 |
| D17 | phase is outside the declared phase vocabulary | 0.01 | 0.2 |
| D19 | record field count exceeds the local shape upper bound | 0.01 | 0.2 |
| D20 | the same object has conflicting adopted values | 0.01 | 0.2 |
| D21 | record field count falls below the local shape lower bound | 0.01 | 0.2 |

D18's undisclosed eight-record ceiling is retired. Eleven coherent samples are not a
defect by count alone. Compactness is explained through origin/terminal coverage, phase
coverage and coarse cadence (P21-P23), with independent duplicate/conflicting/nonascending
time checks. S01 records count only as a diagnostic and imposes no maximum or deduction.
Ordinary omission loses positive coverage; root-cause keys deduplicate actual contradictions.

## Lenient lens

The file must parse as nonempty JSONL with all six required top-level members, all items
decided, every `HANDOFF_ITEMS` result positive, and no `UNUSABLE_DEDUCTIONS` fired, as
explicitly enumerated in `tests/validator.py`. This is separate from the weighted strict
score; target/routing/scaffold quality does not replace local row derivation checks.
