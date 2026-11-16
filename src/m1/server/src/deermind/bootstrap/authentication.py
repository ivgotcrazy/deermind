"""只在API启动时装配认证实现和环境边界。"""

from deermind.product.accounts.auth import AuthService
from deermind.product.public.auth_config import AuthConfig
from deermind.product.public.authentication import Authentication
from sqlalchemy.ext.asyncio import AsyncEngine


async def configure_authentication(engine: AsyncEngine) -> tuple[Authentication, AuthConfig]:
    config = AuthConfig.from_environment()
    service = AuthService(engine)
    await service.initialize()
    return service, config
