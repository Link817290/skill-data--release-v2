FROM harbor-claude-code-aggregated:1.3
USER root
WORKDIR /workspace
RUN python3 -c "import openpyxl, docx"
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN python3 -c "from pathlib import Path; p=Path('/workspace/materials'); assert len(list(p.glob('*.docx')))==3; assert len(list(p.glob('*.pdf')))==2; assert all(x.stat().st_size>0 for x in p.iterdir())" && mkdir -p /workspace/output /logs/verifier /logs/artifacts && chown -R 20005:0 /workspace /logs
RUN test ! -e /tests/scoring_params.json && test ! -e /workspace/output/linkage-test-cases.xlsx
USER 20005
