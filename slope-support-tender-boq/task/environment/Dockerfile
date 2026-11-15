FROM harbor-claude-code-aggregated:1.3 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir -p /logs /workspace /workspace/output
COPY workspace/ /workspace/
RUN chown -R 20005:0 /logs /workspace

# 自检：随包两张图都要能转出实体。转不出要在构建期暴露，不能留到跑批时
# 才发现图是打不开的。每张图用各自的输出名——dwg2dxf 不覆盖已有文件。
RUN for f in /workspace/*.dwg; do \
        out="/tmp/$(basename "$f" .dwg).dxf"; \
        rm -f "$out"; \
        dwg2dxf -o "$out" "$f" >/dev/null 2>&1 || exit 1; \
        python3 -c "import ezdxf,sys; d=ezdxf.readfile(sys.argv[1]); n=len(list(d.modelspace())); print(sys.argv[1], 'entities', n); sys.exit(0 if n>100 else 1)" "$out" || exit 1; \
        rm -f "$out"; \
    done

WORKDIR /workspace
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=20005:0 skills/ /skills/
