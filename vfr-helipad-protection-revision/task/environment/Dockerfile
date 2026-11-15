# 任务环境镜像 —— 照抄，只准改标了「可改」的两段。
#
# 为什么不让你自己写：三个已验收包的 Dockerfile 骨架逐行相同，差异只在依赖和断言。
# 而本批 10 个包里有 3 个自己挑了 ubuntu:22.04 / python:3.11-slim / python:3.12-slim，
# harbor 的 claude-code agent 在 setup 阶段探测已装 CLI，裸镜像探测返回空，
# 报 `Agent install failed: 'NoneType' object has no attribute 'strip'`，整轮无结果。
#
# 基础镜像有机械闸把关（判最后一个 FROM），写错冻结不了，也就拿不到 rollout 算力。

FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace

# ── 可改 1：本任务需要的系统依赖。不需要就把整段删掉 ──────────────────
# 常见：poppler-utils（PDF 抽文本）、libreoffice（办公格式转换）、
#       fonts-noto-cjk（中文渲染）、unzip
# 依赖已烤进基础镜像 1.3 就整块跳过 —— 连 apt-get update 都不跑，
# 那一步本身就要连 Debian 源，是离线构建失败的真正原因。
RUN command -v pdftotext >/dev/null 2>&1 && command -v tesseract >/dev/null 2>&1 \
 || ( apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr \
 && rm -rf /var/lib/apt/lists/* )

# wheel 随包走，--no-index 保证完全不碰网络。
COPY wheels /tmp/wheels

RUN pip install --no-index --find-links=/tmp/wheels --no-cache-dir ezdxf==1.4.4

COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# ── 可改 2：断言材料确实进了镜像 ────────────────────────────────────
# 漏 COPY 会静默跑空——作答者进去看到空目录，整批 rollout 白跑且不报错。
# 每个材料文件都写一条，交付物有 output 目录就一并建出来。
RUN test -s /workspace/legacy_airfield_criteria.pdf \
    && test -s /workspace/current_airfield_criteria.pdf \
    && mkdir -p /workspace/output

# ── 以下不准改 ──────────────────────────────────────────────────
# 归档轨迹的进程用宿主机 uid 读 agent 产物；容器里若以 root 写，
# 属主变成 root:root、轨迹 jsonl 是 0600，宿主机读不了，
# 轨迹转换失败 → 整条 trial 无分无产物。范式一有 302 条栽在这里。
RUN chown -R 20005:0 /workspace
USER 20005

CMD ["/bin/sh"]
