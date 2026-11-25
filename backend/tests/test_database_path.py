"""数据库引擎的连接串解析。

盯的是一个会让**数据静默丢失**的故障：``_init_engine()`` 早先对 SQLite
完全无视 ``DATABASE_URL`` 里的路径，总是按模块位置推算
``<backend>/agentflow.db``。于是：

  * ``alembic`` 按 ``settings.DATABASE_URL`` 把表建在 ``/data/agentflow.db``；
  * 应用自己读写 ``/app/agentflow.db``，还顺手 ``create_all`` 了一份同样的表；
  * 两个库都「看起来正常」—— 迁移日志成功、注册登录都通。直到容器重建，
    所有用户与数据一起消失。

这类问题的可怕之处在于**没有任何报错**，只能靠「引擎真实 URL」来发现。
"""
import pathlib

from app.core import database


def _fresh_engine(monkeypatch, url: str):
    """把连接串换成 url 并清掉已缓存的引擎，返回新建的引擎。"""
    monkeypatch.setattr(database.settings, "DATABASE_URL", url)
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_async_session", None)
    return database.get_engine()


class TestSqliteUrlResolution:
    def test_respects_absolute_path_in_url(self, tmp_path, monkeypatch):
        """核心：连接串里的绝对路径必须被真的用上。"""
        target = tmp_path / "nested" / "custom.db"
        engine = _fresh_engine(monkeypatch, f"sqlite+aiosqlite:///{target}")

        assert pathlib.Path(str(engine.url.database)) == target

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        """目录不存在时要自动建 —— 否则首次连接直接失败。"""
        target = tmp_path / "a" / "b" / "custom.db"
        assert not target.parent.exists()

        _fresh_engine(monkeypatch, f"sqlite+aiosqlite:///{target}")

        assert target.parent.is_dir()

    def test_relative_path_is_kept(self, tmp_path, monkeypatch):
        """相对路径按原样交给 SQLAlchemy（相对于工作目录），不要自作主张改写。"""
        engine = _fresh_engine(monkeypatch, "sqlite+aiosqlite:///./relative.db")

        assert str(engine.url.database) == "./relative.db"

    def test_empty_url_falls_back_to_backend_dir(self, monkeypatch):
        """没配连接串时退回 <backend>/agentflow.db，保持零配置的本地开发行为。

        注意空串本身是**非法**连接串（SQLAlchemy 会抛 ArgumentError），
        这条走的是「没配」的分支 —— 两者别混。
        """
        monkeypatch.setattr(database.settings, "DATABASE_URL", "")
        monkeypatch.setattr(database, "_engine", None)

        engine = database.get_engine()

        assert str(engine.url.database).endswith("agentflow.db")
        assert pathlib.Path(str(engine.url.database)).is_absolute()

    def test_resolver_helper_matches_engine(self, tmp_path, monkeypatch):
        target = tmp_path / "x.db"
        url = f"sqlite+aiosqlite:///{target}"

        assert database._resolve_sqlite_url(url) == url
