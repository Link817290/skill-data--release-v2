FROM harbor-claude-code-aggregated:1.3
USER root
WORKDIR /workspace
RUN python3 -c "import openpyxl"
COPY task/tests/ /tests/
COPY task/instruction.md RUBRIC.md /tests/
COPY task/tests/mix_judge/cache/ /tests/mix_judge/cache/
RUN mkdir -p /workspace/output /logs/verifier && chmod 755 /tests/test.sh && chown -R 20005:0 /workspace /logs
USER 20005
