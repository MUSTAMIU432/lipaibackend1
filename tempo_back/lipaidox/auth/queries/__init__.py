import strawberry
from .user_query import UserQuery
from .email_query import EmailQuery
from .phone_query import PhoneQuery
from .password_query import PasswordQuery
from .token_query import TokenQuery
from .public_config_query import PublicAuthConfigQuery


@strawberry.type
class AuthQuery(
    UserQuery,
    EmailQuery,
    PhoneQuery,
    PasswordQuery,
    TokenQuery,
    PublicAuthConfigQuery,
):
    pass

__all__ = ["AuthQuery"]
