FROM harbor-claude-code-aggregated:1.3
USER root
WORKDIR /workspace
COPY --chown=20005:20005 workspace/ /workspace/
COPY --chown=20005:20005 skills/ /skills/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN python3 -c "import openpyxl, docx, pymupdf" \
    && test -s "/workspace/materials/LG_AKB76043105_Button_Function_Spec.pdf" \
    && test -s "/workspace/materials/LG_AKB76043105_Standard_Test_Procedure_SOP.docx" \
    && test -s "/workspace/materials/MFL72141910_02_S_250218a.pdf" \
    && test -s "/workspace/materials/mmo_120384967_1788973707_747_3631382.pdf" \
    && test -s "/workspace/materials/product-pdf (1).pdf" \
    && test -s "/workspace/materials/output_contract.json" \
    && test -s "/skills/evidence-bound-test-planning/SKILL.md" \
    && mkdir -p /workspace/output \
    && chown 20005:20005 /workspace/output
USER 20005
