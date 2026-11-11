FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
COPY wheels/ /opt/delivery-wheels/
RUN python3 -m pip install --no-index --find-links=/opt/delivery-wheels networkx==3.5 pyproj==3.7.2
COPY workspace/ /workspace/
RUN chown -R 20005:0 /workspace
USER 20005

FROM runtime AS no-skill

FROM runtime AS with-skill
USER root
COPY skills/ /skills/
RUN chown -R 20005:0 /skills
USER 20005
