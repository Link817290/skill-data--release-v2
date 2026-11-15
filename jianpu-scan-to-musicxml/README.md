# Jianpu scan to MusicXML/MEI

Transcribe the supplied two-page historical Chinese score into the required diplomatic MEI file `output/揚州慢.mei`. The MEI must preserve source text, notation classes, source regions, page/column order and the boundary against invented modern notation.

Build the actor image from `task/environment/Dockerfile` and the verifier image from `task/environment/Dockerfile.verifier`; both use `harbor-claude-code-aggregated:1.3`. The with-skill condition exposes the two skills under `task/environment/skills/`; the no-skill condition receives the same source pages without them.

Run the Oracle with `task/solution/solve.sh WORKSPACE`. Run scoring with `task/tests/test.sh WORKSPACE/output/揚州慢.mei`. The evaluator is deterministic and reads only the submitted MEI, the packaged source pages and source-derived ground truth.
