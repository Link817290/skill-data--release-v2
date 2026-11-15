FROM harbor-claude-code-aggregated:1.3
USER root
WORKDIR /workspace
COPY workspace/ /workspace/
RUN python3 -c "import pathlib; p=pathlib.Path('/workspace/materials'); assert p.is_dir(); assert any(f.stat().st_size > 0 for f in p.glob('*.pdf')); assert any(f.stat().st_size > 0 for f in p.glob('*.docx'))" && mkdir -p /workspace/output /logs/verifier /logs/artifacts && chown -R 20005:0 /workspace /logs
USER 20005
