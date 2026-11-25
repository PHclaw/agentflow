#!/bin/sh
# AgentFlow 后端容器入口。
#
# 顺序很重要：**先跑数据库迁移，再起服务**。
#
# 为什么不交给 app 启动时的 init_db()：它用的是 Base.metadata.create_all，
# 只会新建缺失的表、不会修改已有表的列，而且**不写 alembic_version**。
# 新库若先被 create_all 建出来，版本基线就是空的，之后 alembic upgrade
# 会因为「表已存在」而失败 —— 升级链从此再也接不上，只能手工 stamp。
# 所以这里先 upgrade，之后 uvicorn 里的 create_all 变成一次无害的空操作。
#
# 重试是给 docker compose 用的：即便有 depends_on + healthcheck，
# 数据库容器仍可能比后端晚几秒才真正接受连接。
set -e

ATTEMPTS=0
MAX_ATTEMPTS="${DB_MIGRATE_MAX_ATTEMPTS:-30}"

until alembic upgrade head; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "[entrypoint] 数据库迁移连续失败 ${MAX_ATTEMPTS} 次，放弃启动" >&2
        exit 1
    fi
    echo "[entrypoint] 迁移失败（第 ${ATTEMPTS} 次），2 秒后重试 —— 数据库可能还没就绪" >&2
    sleep 2
done

echo "[entrypoint] 数据库迁移完成，启动：$*"
exec "$@"
