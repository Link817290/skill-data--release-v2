# Cat Meme Mini Theater

Create a 40-second Remotion comedy from the issued screenplay and media. Deliver
`/workspace/output/final.mp4`, `project/`, and `edit-plan.json`.

Build from the package root (Docker build networking may require `--network host`):

```sh
docker build --target runtime -t cat-meme-mini-theater-runtime:20261103 task/environment
docker build --target with-skill -t cat-meme-mini-theater-actor:20261103 task/environment
docker build --target no-skill -t cat-meme-mini-theater-no-skill:20261103 task/environment
docker build -t cat-meme-mini-theater-verifier:20261103 -f task/environment/Dockerfile.verifier .
```

The authorized base is `harbor-claude-code-aggregated:1.3`, with Node 22.23.0,
Remotion 4.0.535, FFmpeg, Chromium, Chinese fonts, and pinned Python verifier
dependencies. Remotion dependencies and npm's offline package cache are installed
at build time. Actor images contain issued inputs and, in the with-skill target,
skills. Golden, solution, tests, and judge credentials are verifier-only.

Harbor uses `task/task.toml`; the no-skill condition uses `task/task_no_skill.toml`.
The actor has no network; the separate verifier uses public networking. The Oracle
`task/solution/solve.sh` honestly copies the authored reference fixture; it is not
an independently generated solution. Harbor must supply the fixture to this
verifier-only Oracle entrypoint. The authored Golden is evaluated separately.

Run `bash task/tests/test.sh /workspace` in the verifier with the candidate at
`/workspace/output`. Fresh scoring is the default and requires externally supplied
`LLM_JUDGE_BASE_URL` (Responses API URL), `LLM_JUDGE_API_KEY`, and optionally
`LLM_JUDGE_MODEL` (default `gpt-5.6-sol`). Credentials must be available only to
the verifier.

Release replay is Golden-only under `task/tests/golden_replay/`: one exact visual,
audio and soundtrack binding for the authored Golden. Ownership and audio
resolution are deterministic for that artifact and require no provider record.
Set `LLM_JUDGE_MODE=replay` for offline Golden verification. A new or changed
artifact must miss these bindings and use fresh judging; ordinary candidate,
and provider-history caches are not shipped. A missing or invalid cache,
provider failure, or unresolved judgment exits nonzero and removes numeric rewards.
Successful `reward.json` contains only numeric `strict` and `lenient` values;
evidence is in `reward_detail.json`.

`LLM_JUDGE_CACHE_DIR` selects the cache root and
`LLM_JUDGE_TIMEOUT_SECONDS` sets the Responses transport timeout (default 600).

Strict uses the `integrated_delivery_v1` policy declared in
`task/tests/scoring_params.json`; lenient is an independent minimum-usable-film
conjunction. `RUBRIC.md` gives the professional dependency rationale and scored
owner boundaries; numeric settlement remains defined by the evaluator contract.

The brief explicitly preserves source role voices and the screenplay's specific
performances, while soundtrack effects may use equivalent designs.
