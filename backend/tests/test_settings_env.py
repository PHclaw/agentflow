"""Settings 对**环境变量**的解析。

这里盯的是一个真实故障：``CORS_ORIGINS`` 声明成 ``List[str]`` 并写了
逗号分隔的校验器，字段注释也明确写着「支持逗号分隔字符串，便于
docker-compose 注入」——

但 pydantic-settings 对 List 这类复杂类型会**先**做一次 json.loads，
逗号串在那一步就抛 ``SettingsError`` 让进程起不来，```field_validator``
根本没机会执行。

本地开发一直没暴露，因为开发环境从不设这个环境变量（走的是默认值）。
一旦按 docker-compose 的写法注入，整个后端就是崩溃重启循环，日志里只有
一句 ``error parsing value for field "CORS_ORIGINS"``。
"""
import pytest


class TestCorsOriginsEnvParsing:
    def test_accepts_comma_separated(self, monkeypatch):
        """docker-compose / .env 里好写的形式：逗号分隔。"""
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8001")

        from app.core.config import Settings

        assert Settings().CORS_ORIGINS == [
            "http://localhost:3000",
            "http://localhost:8001",
        ]

    def test_comma_separated_tolerates_spaces(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://a ,  http://b ,http://c")

        from app.core.config import Settings

        assert Settings().CORS_ORIGINS == ["http://a", "http://b", "http://c"]

    def test_still_accepts_json_array(self, monkeypatch):
        """JSON 数组是改动前**唯一**能用的形式，不能因为这次修复而挂掉。"""
        monkeypatch.setenv("CORS_ORIGINS", '["http://a","http://b"]')

        from app.core.config import Settings

        assert Settings().CORS_ORIGINS == ["http://a", "http://b"]

    def test_single_origin(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://only.example.com")

        from app.core.config import Settings

        assert Settings().CORS_ORIGINS == ["https://only.example.com"]

    def test_falls_back_to_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        from app.core.config import Settings

        assert "http://localhost:5173" in Settings().CORS_ORIGINS

    def test_does_not_raise_settings_error(self, monkeypatch):
        """核心断言：以前这里抛的是 SettingsError（进程起不来），不是解析错。

        单独写一条是因为「不抛异常」本身就是修复点，和上面的值断言不是一回事。
        """
        monkeypatch.setenv("CORS_ORIGINS", "http://x,http://y")

        from app.core.config import Settings

        Settings()  # 不抛异常即通过


class TestEnvKeysMatchSettingsFields:
    """``.env.example`` 里的键必须真的对应 Settings 字段。

    pydantic-settings 认不出的键会被**静默忽略**，不报错也不警告。
    ``.env.example`` 里曾经有 ``ACCESS_TOKEN_EXPIRE_MINUTES`` /
    ``APP_DEBUG`` / ``APP_URL`` 三个键，代码里根本没有 —— 照着填的人
    会以为改了 token 有效期，实际什么都没发生。
    """

    def test_example_keys_are_real_fields(self):
        import pathlib
        import re

        from app.core.config import Settings

        example = (
            pathlib.Path(__file__).resolve().parents[2] / ".env.example"
        )
        if not example.is_file():
            pytest.skip(".env.example 不在预期位置")

        known = set(Settings.model_fields)
        # compose 自己读的端口映射变量，应用代码不认，不算配置键
        compose_only = {"FRONTEND_PORT", "BACKEND_PORT"}
        # 这几个是部署时才会用到的容器专用变量名，不在 Settings 里
        compose_only |= {"AGENTFLOW_DOCKER_DATABASE_URL", "AGENTFLOW_DOCKER_REDIS_URL"}

        unknown = []
        for line in example.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Z][A-Z0-9_]*)\s*=", line)
            if not m:
                continue
            key = m.group(1)
            if key not in known and key not in compose_only:
                unknown.append(key)

        assert not unknown, (
            "这些键在 Settings 里不存在，填了也是静默无效："
            + "、".join(sorted(set(unknown)))
        )
