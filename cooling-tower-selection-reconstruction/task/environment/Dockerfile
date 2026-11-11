FROM harbor-claude-code-aggregated:1.3 AS actor
USER root
WORKDIR /workspace
COPY workspace/materials/ /workspace/materials/
RUN python3 -c "import pathlib,site,openpyxl; pathlib.Path(site.getsitepackages()[0], 'cooling_dependencies.pth').write_text(str(pathlib.Path(openpyxl.__file__).resolve().parents[1]) + '\n')"
RUN mkdir -p /workspace/output && chown -R 20005:0 /workspace && python3 -c "import openpyxl" && command -v libreoffice && test ! -e /tests && test ! -e /solution
RUN env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp python3 -c "import openpyxl,et_xmlfile"
USER 20005

FROM actor AS no-skill

FROM actor AS with-skill
USER root
COPY skills/ /skills/
RUN chown -R 20005:0 /skills && ! rg -n -i 'golden|validator|reward|rubric|oracle|/tests|/solution' /skills
USER 20005
