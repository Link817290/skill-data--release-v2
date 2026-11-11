# constrained-dc-network-design

This package asks an agent to produce an auditable Excel recommendation for a capacity-constrained distribution-center footprint and its single-facility outage recovery plan.

## Release Structure

The release has six root entries:

| Path | Purpose |
| --- | --- |
| `README.md` | Package interface and verification commands |
| `MANIFEST.json` | SHA-256 and byte inventory of delivered files |
| `RUBRIC.md` | Human-readable strict and lenient contract |
| `dataset.toml` | Dataset identity, conditions and scorer declaration |
| `golden/` | Reference planning workbook |
| `task/` | Instruction, environment, source material, skills, reference builder and verifier |

## Environment Build

```bash
docker build -t constrained-dc-network-design -f task/environment/Dockerfile task/environment
```

The image installs the delivered OpenPyXL and PuLP wheels without network access and places the source workbook in `/workspace`.

## With-Skill And No-Skill Conditions

- `task/task.toml` declares the with-skill condition and mounts `task/environment/skills/`.
- `task/task_no_skill.toml` declares the no-skill condition and omits the skills mount.

Both conditions use the same instruction, material, deliverable path and verifier.
Both also declare a mixed continuous judge: the program Oracle settles closed workbook facts and the required Responses judge settles open professional meaning.

## Instruction And Material

- Agent instruction: `task/instruction.md`
- Packaged source workbook: `task/environment/workspace/Supply chain logisitcs problem.xlsx`
- In-image source workbook: `/workspace/Supply chain logisitcs problem.xlsx`

The source is read-only task material. Current product, customer, port, tariff, cost and capacity relationships control the recommendation.

## Output

The required deliverable is `/workspace/network_design_recommendation.xlsx`. Both task conditions declare that exact file as a captured artifact named `network_design_recommendation.xlsx`. It must contain the primary footprint and allocation, explicit exceptions, all used-facility outage comparisons, governing-outage recovery, facility reconciliation, correct economics and live cross-sheet lineage.

## Reference Build

```bash
python -B task/solution/reference_solution.py \
  --source "task/environment/workspace/Supply chain logisitcs problem.xlsx" \
  --output /tmp/network_design_recommendation.xlsx
```

`task/solution/solve.sh` is the task-image reference builder and defaults to `/workspace/network_design_recommendation.xlsx`.

## Program Oracle And Scorer

```bash
python -B task/tests/validator.py /tmp/network_design_recommendation.xlsx \
  --source "task/environment/workspace/Supply chain logisitcs problem.xlsx" \
  --ground-truth task/tests/ground_truth.json
```

The Oracle reads owner weights and semantics from `task/tests/scoring_params.json` and returns strict reward, lenient reward, P01-P08 completion, damage and settlement detail. `task/tests/test.sh` is the verifier-container entrypoint; it reads the default deliverable and source under `/workspace` and writes reward files under `/logs/verifier/`.

## External Judge: Fresh And Exact Replay

After the program Oracle, required `task/tests/mix_judge/gate_runtime.py score` calls a source-bound external judge for open professional explanations, assertion polarity, external-source reliance, task-text violations and anti-gaming. Closed numeric/formula facts remain program-owned. The semantic owner enters the final ledger by preserving the program reward or setting a failed semantic submission to zero; keyword presence alone cannot pass it.

For a fresh call, configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY` and optionally `LLM_JUDGE_MODEL` (default and only qualified model: `gpt-5.6-sol`). The transport uses OpenAI Responses at `/v1/responses`. For exact replay, the orchestrator supplies a previously bound response and invokes the same interface with network disabled.

```bash
python -B task/tests/mix_judge/gate_runtime.py score \
  --installed task/tests/mix_judge \
  --deliverable-dir /tmp/network-deliverable \
  --program-detail /tmp/program_reward_detail.json \
  --out /tmp/network-verifier-output
```

## UNMEASURED And Failure Handling

An unavailable external judge is infrastructure state, not a fabricated business failure. The required gate records `UNMEASURED`, removes numeric reward files and exits nonzero.

A missing or unreadable required workbook is a missing business deliverable and earns no capability credit. Malformed owner parameters or incomplete owner-basis declarations are rejected before settlement.

## Expected Golden Result

The delivered Golden workbook yields strict `1.0` and lenient `1.0` through both the program Oracle and complete verifier entrypoint.
