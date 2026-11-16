FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
COPY --chown=20005:0 workspace/ /workspace/
RUN test -d /workspace/materials \
    && test -f '/workspace/materials/01-劳动合同书.docx' \
    && install -d -o 20005 -g 0 -m 755 /workspace/output /home/agent \
    && chown -R 20005:0 /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

FROM runtime AS actor-no-skill
USER 20005
CMD ["bash"]

FROM runtime AS actor-with-skill
USER root
COPY --chown=20005:0 skills/ /skills/
USER 20005
CMD ["bash"]
