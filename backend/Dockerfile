# AgentFlow 后端镜像
#
# 构建上下文是**仓库根**（见 docker-compose.yml 的 context: .），
# 因为镜像里要同时带上 backend/ 源码和 skills/、config/、static/ 这三份
# 技能运行时依赖的仓库资源。
#
#   docker build -f backend/Dockerfile -t agentflow-backend .
#
# 构建不出国内网络时，用镜像源覆盖基础镜像（见下）：
#   docker build --build-arg BASE_REGISTRY=docker.m.daocloud.io \
#     -f backend/Dockerfile -t agentflow-backend .
#
# Python 版本与本地开发环境一致（3.13）：requirements-docker.txt 是从那个
# 环境 pip freeze 出来的，换 Python 大版本可能解析出不同的轮子。
ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/library/python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# 中文字体：Skill 出图走 matplotlib，缺字体时图表里的中文全是方框。
# 不装 gcc/libpq-dev —— requirements-docker.txt 里的包都有 manylinux 轮子，
# 真需要编译时构建会直接失败，那时再补，别提前把编译链带进镜像。
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# pip 源。国内构建时 pip 走公网会很慢甚至超时，可以覆盖：
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ...
# 用 --index-url 传给这一次安装，而不是设成 ENV —— 免得镜像里长期留着一个
# 会改变后续 pip 行为的全局配置。
ARG PIP_INDEX_URL=https://pypi.org/simple

# 依赖单独一层：只改代码时不必重装依赖
COPY backend/requirements-docker.txt /app/requirements-docker.txt
RUN pip install --index-url "${PIP_INDEX_URL}" -r /app/requirements-docker.txt

# 后端源码。backend/.venv、__pycache__、*.db、.env 由根目录的 .dockerignore 排除
COPY backend/ /app/

# 技能运行时需要的仓库资源。运行时可被 compose 的 bind mount 覆盖
COPY config/ /repo/config/
COPY static/ /repo/static/
COPY skills/ /repo/skills/

RUN mkdir -p /repo/uploads /repo/static/generated

ENV AGENTFLOW_REPO_ROOT=/repo \
    AGENTFLOW_UPLOADS_DIR=/repo/uploads \
    DATABASE_URL=sqlite+aiosqlite:////data/agentflow.db

COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 以 root 运行是有意为之：compose 把 skills/、uploads/、static/ 以 bind mount
# 挂进来（方便直接在宿主机上增删技能、看产物），那些目录在宿主机上的属主
# 未必对应镜像里的某个 uid，非 root 会写不进去 —— 表现是「管理员建技能报
# 500」「上传文档失败」。若你的部署不需要 bind mount，可以自行加
# USER 1000:1000 收紧。
VOLUME ["/data", "/repo/uploads", "/repo/static"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else 1)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
