# n8n + python3 + uv + aws-cli
# Execute Command 노드가 컨테이너 안에서 `python3 /repo/.../*.py` 를 돌리려면
# 기본 n8n 이미지에 파이썬과 aws-cli 를 넣어야 한다.
# 2026-07 주의: n8nio/n8n:latest 는 Docker Hardened Image 로 바뀌어 apk(패키지 매니저)가 없다.
# → uv 정적 바이너리를 COPY 해서 관리형 파이썬 + awscli(uv tool)를 설치하는 방식으로 우회한다.
# 무거운 임베딩(marqo/torch)은 이 컨테이너가 아니라 호스트/GPU 워커에서 도는 것을 권장.
FROM ghcr.io/astral-sh/uv:latest AS uv

FROM n8nio/n8n:latest

USER root

COPY --from=uv /uv /uvx /usr/local/bin/

# 파이썬은 /opt/uv 아래(전역 읽기 가능)에 설치 — n8n 은 node 유저로 돌기 때문
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/pythons \
    UV_TOOL_DIR=/opt/uv/tools \
    UV_TOOL_BIN_DIR=/usr/local/bin

RUN uv python install 3.12 \
    && ln -sf "$(uv python find 3.12)" /usr/local/bin/python3 \
    && python3 --version \
    && uv tool install awscli \
    && aws --version \
    && uv pip install --system --break-system-packages pyarrow pandas numpy jsonschema \
    && chmod -R a+rX /opt/uv

USER node
