# AgentFlow 前端镜像
#
# 构建上下文是 ./frontend（见 docker-compose.yml）。
#
#   docker build -t agentflow-frontend ./frontend
#
# 构建不出国内网络时，用镜像源覆盖基础镜像（见下）：
#   docker build --build-arg BASE_REGISTRY=docker.m.daocloud.io -t agentflow-frontend ./frontend
#
# 两阶段：builder 里跑 tsc + vite build，runner 只留 nginx 和静态产物 ——
# node_modules（数百 MB）和源码都不进最终镜像。
#
# 用 node:20-slim 而不是 alpine：vite/rollup 的原生绑定在 musl 上偶发解析
# 不到，构建报错信息还很晦涩。slim 只影响构建阶段，最终镜像仍是 nginx:alpine。
ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/library/node:20-slim AS builder

# npm 源。国内构建可覆盖（npmmirror 通常快很多）：
#   docker build --build-arg NPM_REGISTRY=https://registry.npmmirror.com ...
ARG NPM_REGISTRY=https://registry.npmjs.org

WORKDIR /app

# 先只拷依赖清单，让这层能被缓存 —— 只改业务代码时不必重装依赖
COPY package.json package-lock.json ./
# npm ci 而不是 npm install：严格按 lockfile 安装，保证构建可复现
RUN npm ci --registry="${NPM_REGISTRY}"

COPY . .
# npm run build == tsc && vite build，类型不过就构建失败（有意如此）
RUN npm run build


FROM ${BASE_REGISTRY}/library/nginx:alpine AS runner

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
