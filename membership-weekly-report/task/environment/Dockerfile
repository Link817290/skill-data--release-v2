# 基础镜像必须带版本号。不写的话 docker 会补 :latest 去外网拉，而测评机器出不去
# 外网，构建会以一个看起来像网络故障的超时失败。
FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# openpyxl 读两份 xlsx 材料；python-docx 读写 会员周报模板.docx 和产出的
# output/weekly_report.docx。两边都靠这两个包。
RUN python3 -c "import openpyxl, docx; assert openpyxl.__version__ == '3.1.5'"

# 只复制 workspace/。原提交是 `COPY . /app/environment/`，构建上下文是
# environment/，那会把 environment/skills/ 一起烤进镜像——no-skill 组即使不挂
# skill 也能在容器里读到它，两组的条件就不再互斥了。skills/ 留在构建上下文之外，
# 由 harness 按 task.toml / task_no_skill.toml 决定挂不挂。
WORKDIR /app/environment
RUN mkdir -p /app/environment /logs /workspace/output
COPY --chown=1000:1000 workspace/ /workspace/
RUN ln -s /workspace/materials /app/environment/materials \
    && ln -s /workspace/output /app/environment/output \
    && chown -R 1000:1000 /app /logs /workspace

# 构建期自检：workspace 没复制进来是静默失败，跑出来是空轮而不是报错。
RUN test -s "/workspace/materials/2024会员数据明细更新至0322.xlsx" \
    && test -s "/workspace/materials/2024会员项目进度更新至0322.xlsx" \
    && test -s "/workspace/materials/会员周报模板.docx"

USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/
