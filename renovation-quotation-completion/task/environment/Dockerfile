FROM harbor-claude-code-aggregated:1.3
USER root
COPY workspace/ /workspace/
COPY wheels/ /opt/quotation-wheels/
RUN python3 -m pip install --no-index --no-deps --find-links=/opt/quotation-wheels openpyxl==3.1.5 xlrd==2.0.2 et-xmlfile==2.0.0
RUN python3 -c "import pathlib, openpyxl, xlrd; assert pathlib.Path('/workspace/materials').is_dir()"
RUN mkdir -p /workspace/output && chown -R 20005:0 /workspace
USER 20005
WORKDIR /workspace
