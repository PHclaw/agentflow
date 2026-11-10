"""
核心配置
"""
import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode
from typing import Annotated, Any, List
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "AgentFlow"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # 数据库 - SQLite 备用方案
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentflow.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # LLM 配置
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-haiku"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # Skill 运行时（Model Lab 兼容）
    DASHSCOPE_API_KEY: str = ""
    MODEL_BASE_URL: str = ""
    CHATZOC_API_KEY: str = ""
    CHATZOC_BASE_URL: str = ""
    CHATZOC_AGENT_TYPE: str = "chatzoc_9b_B"
    DEFAULT_MODEL: str = ""
    OPTIMIZE_MODEL: str = ""
    SEMANTIC_SCHOLAR_API_KEY: str = ""
    
    # Embedding
    # 向量端点单独配置：知识库要用向量模型，通常和对话模型不是同一个，
    # 不该为了知识库去改「设置」里正在用的对话模型。
    # 本地 ollama 只需填 EMBEDDING_BASE_URL=http://localhost:11434/v1，无需密钥。
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # 大模型 API 配置热加载：生效配置的快照最多缓存多少秒
    # 同一进程内改完立即生效；多 worker 部署下最迟该秒数后一致
    LLM_CONFIG_CACHE_TTL_SECONDS: int = 5
    # 连接测试超时（秒）
    LLM_CONFIG_TEST_TIMEOUT: int = 20
    
    # PiAgent 运行时（可选引擎，参考 AlphaLens 的 piagent 实现）
    # 开启后可通过 /api/v1/pi/{agent_id}/stream 调用外部 agent CLI（pi）
    PIAGENT_ENABLED: bool = False
    PIAGENT_EXE: str = "pi"
    PIAGENT_TIMEOUT: int = 180
    # pi 默认 provider 是 google；这里可覆盖成 openai/anthropic 等与项目一致的厂商
    PIAGENT_PROVIDER: str = ""
    PIAGENT_MODEL: str = ""
    # 每个 Agent 一个独立工作区；留空则用 uploads/pi_workspace/<agent_id>
    PIAGENT_WORKSPACE_ROOT: str = ""
    # 技能目录；留空则用仓库根的 skills/
    PIAGENT_SKILLS_DIR: str = ""
    
    # 外部只读数据源（ERP）连接器：供工作流 erp_read 工具节点调用
    EXTERNAL_CONNECTORS_ENABLED: bool = True
    # 单次读取的默认 / 最大行数（连接器配置再小也只到这两个为止）
    CONNECTOR_DEFAULT_ROW_LIMIT: int = 200
    CONNECTOR_MAX_ROW_LIMIT: int = 2000
    # 连接 / 查询超时（秒）
    CONNECTOR_TIMEOUT_SECONDS: int = 10
    
    # CORS（支持逗号分隔字符串，便于 docker-compose 注入）
    #
    # ``NoDecode`` 不能去掉：pydantic-settings 对 List 这类复杂类型会**先**
    # 尝试 json.loads，失败即抛 SettingsError 让进程起不来 —— 那个 JSON 解码
    # 发生在下面这个 field_validator 之前，所以光写校验器接不住逗号分隔串。
    # 结果是「本地开发一切正常（因为从不设这个环境变量），一上 docker-compose
    # 设了 CORS_ORIGINS 就再也起不来」。
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """两种写法都要认。

        - JSON 数组 ``["http://a"]``：pydantic-settings 原本唯一接受的形式，
          已经这么配的部署不能因为这次改动而挂掉；
        - 逗号分隔 ``http://a,http://b``：docker-compose / .env 里好写得多，
          也是这个字段注释一直声称支持的写法。
        """
        if isinstance(v, str):
            raw = v.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
            return [x.strip() for x in raw.split(",") if x.strip()]
        return v
    
    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # 各档额度。**只在这里定义一份**：套餐文案、额度判定、用量接口都从
    # 这里取，避免出现「宣传 20 个 Agent、实际按 5 个判」这类不一致。
    FREE_AGENTS: int = 1
    FREE_MESSAGES: int = 5
    PRO_AGENTS: int = 5
    PRO_MESSAGES: int = 150
    TEAM_AGENTS: int = 20
    TEAM_MESSAGES: int = 666
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_FREE: str = ""
    STRIPE_PRICE_PRO: str = "price_pro_monthly"
    STRIPE_PRICE_TEAM: str = "price_team_monthly"

    # ===== 邮件（注册验证码）=====
    # MAIL_ENABLED=false 时不会真的发信，验证码只打印到日志，
    # 方便本地开发与自动化测试（见 services/mailer.py）
    MAIL_ENABLED: bool = False
    MAIL_HOST: str = ""              # 如 smtp.qq.com / smtp.163.com
    MAIL_PORT: int = 465             # 465 用 SSL，587 用 STARTTLS
    MAIL_USER: str = ""              # 完整邮箱地址，如 you@qq.com
    MAIL_PASSWORD: str = ""          # 邮箱「授权码」，不是登录密码
    MAIL_FROM: str = ""              # 留空则用 MAIL_USER
    MAIL_FROM_NAME: str = "AgentFlow"
    MAIL_USE_SSL: bool = True        # 465 为 True；587 改为 False
    MAIL_TIMEOUT: int = 10
    # 邮件页头的 logo 图片地址（建议 68×68 的方形 PNG，走 HTTPS）。
    # 留空时用「色块 + 首字母」画一个 —— 多数客户端默认不加载图片，
    # 纯图片标识会让页头开天窗。
    MAIL_LOGO_URL: str = ""

    # 对外可访问的站点地址（协议 + 域名，不带路径），如 https://agentflow.example.com。
    #
    # 邮件里只能靠它引用品牌标识 PNG：内联 <svg> 被 Outlook（Word 排版引擎）
    # 和 Gmail 丢弃，data: base64 图被 Windows 版 Outlook 默认屏蔽，
    # 剩下唯一可靠的方式就是绝对 http/https 地址。
    #
    # 留空则邮件页头退化为纯文字标识（双色字标），不引任何图片 ——
    # 那样在「图片默认不加载」的客户端里也不会开天窗。
    PUBLIC_BASE_URL: str = ""

    # 管理员邮箱白名单，逗号分隔。
    # 匹配到的账号在登录/注册时被授予 admin 角色。
    # 用配置而不是「改数据库」来指定首个管理员：新环境里管理员记录还不存在，
    # 靠手工 UPDATE 起不来；配置一改、登录一次就生效。
    ADMIN_EMAILS: str = ""

    @property
    def admin_email_set(self) -> set[str]:
        """管理员邮箱集合（小写归一）。"""
        return {
            e.strip().lower()
            for e in self.ADMIN_EMAILS.split(",")
            if e.strip()
        }

    # 注册是否必须通过邮箱验证码。
    # 关闭后 /auth/register 不再校验 code，适合自动化测试与内网演示；
    # 生产环境请保持 true，否则邮箱真实性无从保证。
    REQUIRE_EMAIL_CODE: bool = True

    # 验证码策略
    #
    # 有效期别设太短。邮件投递要过发信服务器、收信中继和垃圾过滤，慢的时候
    # 一两分钟才到用户收件箱。5 分钟再配 60 秒重发冷却，就会撞上「码还没到
    # 就已经过期、想重发还得再等一分钟」——用户体感就是「过期太快」。
    # 10 分钟能让最慢的投递也留出操作余量；配 CODE_MAX_ATTEMPTS=5 的试错上限，
    # 拉长有效期并不会明显放大暴力枚举的空间。
    CODE_TTL_SECONDS: int = 600      # 有效期 10 分钟
    CODE_LENGTH: int = 6
    CODE_RESEND_INTERVAL: int = 60   # 同一邮箱重发冷却（秒）
    CODE_HOURLY_LIMIT: int = 5       # 同一邮箱每小时上限
    CODE_MAX_ATTEMPTS: int = 5       # 单个码最多试错次数，超过即作废
    # /auth/send-code 的 IP 级限流。
    # 公司/学校共用出口 IP 时这个值容易误伤，可按需放宽。
    SEND_CODE_IP_LIMIT: int = 10     # 每 IP 每窗口最多发几次
    SEND_CODE_IP_WINDOW: int = 3600  # 窗口长度（秒）

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
