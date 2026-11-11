# Controlled-Device Test Planning

## Task

Create an executable English laboratory test plan for the LG AKB76043105 remote
control and its host platform. The plan covers documented communication, pointer,
button, voice, range and universal-control behavior. It must distinguish proposed
tests from execution results and preserve source applicability where supplied
documents describe different variants or event definitions. The actor instruction
is `task/instruction.md`; final scoring responsibilities are in `RUBRIC.md`.

## Inputs

The actor reads the original product evidence and public output contract from
`task/environment/workspace/materials/`:

- `LG_AKB76043105_Button_Function_Spec.pdf`
- `LG_AKB76043105_Standard_Test_Procedure_SOP.docx`
- `MFL72141910_02_S_250218a.pdf`
- `mmo_120384967_1788973707_747_3631382.pdf`
- `product-pdf (1).pdf`
- `output_contract.json`

The with-skill condition additionally registers
`task/environment/skills/evidence-bound-test-planning/` at `/skills`. The
no-skill condition receives the same materials without task skills.

## Deliverable

Write one workbook to
`/workspace/output/LG_AKB76043105_Test_Case_List_EN.xlsx`. Equivalent English
headers, case IDs, case counts and sheet layouts are accepted when the required
roles remain identifiable. Test Result remains blank and Test Status remains
planned/unexecuted. The authored reference is
`golden/LG_AKB76043105_Test_Case_List_EN.xlsx`.

## Runtime And Isolation

All images use `harbor-claude-code-aggregated:1.3`; actors run offline as UID
20005. Build the three declared images from the package root:

```sh
docker build -t controlled-device-test-planning:1.0 -f task/environment/Dockerfile task/environment
docker build -t controlled-device-test-planning-no-skill:1.0 -f task/environment/Dockerfile.no_skill task/environment
docker build -t controlled-device-test-planning-verifier:1.0 -f task/environment/Dockerfile.verifier .
```

Only the with-skill actor contains `/skills`. Neither actor contains tests,
Golden or the Oracle solution. The separate verifier contains `/tests` and no
task skill. `task/task.toml` and `task/task_no_skill.toml` select the corresponding
actor image and the same private verifier image.

## Oracle

`task/solution/solve.sh` invokes `task/solution/solve.py`, which extracts facts
from the original materials and applies explicit engineering rules. It does not
read Golden or scoring files. In an isolated actor workspace, mount only the
solution at `/solution:ro` and run:

```sh
bash /solution/solve.sh /workspace
```

`task/solution/derive_ground_truth.py --check` independently confirms that the
source-derived Oracle bytes match both the root Golden and the private verifier
Golden. XLSX member order, timestamps and platform metadata are canonicalized.

## Scoring And Verification

The private mixed-judge entrypoint is `task/tests/test.sh`; its deterministic
extraction/settlement is `task/tests/validator.py`, while
`task/tests/source_bound_judge.py` is required for test intent, causal isolation,
equivalent actions/expectations and affirmative professional damage. Regex and
keywords only extract candidate evidence. The frozen public contract is
`task/rubric-contract.json`; `task/tests/scoring_params.json` is its hash-bound
runtime view. To score a workspace mounted read-only at `/workspace`, run:

```sh
bash /tests/test.sh /workspace
```

Strict score is positive capability completion multiplied by independent
affirmative-damage retention. Lenient is the conjunction of instruction-domain
coverage, absence of affirmative route/clock/measurement-object conflation, and
absence of fabricated execution results. There is no fixed final-score ceiling.
`reward.json` contains `reward`, `reward_strict` and `reward_lenient`;
`reward_detail.json` contains assertion, damage and readiness ledgers. One exact
Golden-only replay is packaged and never exposed to actors. Every non-Golden
artifact requires verifier-only fresh OpenAI Responses access through
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY` and the fixed default
`LLM_JUDGE_MODEL=gpt-5.6-sol`. `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`
(`auto`, `fresh` or `replay`) and positive `LLM_JUDGE_TIMEOUT_SECONDS` complete
the shared verifier interface. Chat or Anthropic Messages protocols, model
mismatch, cache miss and service failure are UNMEASURED and write no numeric reward.
