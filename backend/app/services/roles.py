"""
角色授予。

管理员身份由 ``ADMIN_EMAILS`` 配置决定，在登录 / 注册时落到 ``users.role``。

为什么不是「查库实时判断」而要把结果写进列：

- 管理接口每次请求都要判权限，查配置字符串比查列更容易写错（大小写、
  空格、末尾逗号）；
- 角色需要出现在 ``/users/me`` 里给前端做入口显隐，落库后只读一个字段。

为什么用配置而不是「手工 UPDATE 数据库」来决定首个管理员：

- 全新部署时管理员记录还不存在，改库这条路根本走不通；
- 配置一改、登录一次就生效，不需要连数据库。
"""
import logging

from ..core.config import settings
from ..models.user import User, UserRole

logger = logging.getLogger(__name__)


def apply_configured_role(user: User) -> bool:
    """按 ``ADMIN_EMAILS`` 授予管理员角色。

    返回是否发生了变更，调用方据此决定要不要 commit。

    **只授予、不回收**。移除配置项不会把已有管理员降级：

    - 登录时静默降级一个正在用后台的账号，体验上更像 bug 而不是策略；
    - 手工提权过的账号会被配置悄悄覆盖掉。

    需要撤销权限时走显式操作（改库或后续的「成员管理」界面），
    让降级永远是一个有人为意图的动作。
    """
    if not user.email:
        return False

    admins = settings.admin_email_set
    if not admins:
        return False

    if user.email.strip().lower() not in admins:
        return False

    if user.role == UserRole.ADMIN.value:
        return False

    user.role = UserRole.ADMIN.value
    logger.info("账号 %s 命中 ADMIN_EMAILS，已授予管理员角色", user.email)
    return True
