FROM python:3.12-slim

# claude CLI (연구실 own-claude 모드용) — node 20
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code @openai/codex

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY web/dist ./web/dist
RUN pip install --no-cache-dir ".[web,deploy]"

ENV DATA_DIR=/data
# 비편집 설치라 소스 상대경로로는 web/dist를 찾지 못한다 — 복사한 위치를 명시
ENV HORCRUX_WEB_DIST=/app/web/dist
EXPOSE 8765
CMD ["horcrux", "serve", "--host", "0.0.0.0"]
