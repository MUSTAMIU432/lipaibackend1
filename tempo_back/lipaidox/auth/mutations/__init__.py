import strawberry
from .user_mutation import UserMutation
from .email_mutation import EmailMutation
from .phone_mutation import PhoneMutation
from .password_mutation import PasswordMutation
from .two_factor_mutation import TwoFactorMutation

@strawberry.type
class AuthMutation(UserMutation, EmailMutation, PhoneMutation, PasswordMutation, TwoFactorMutation):
    pass

__all__ = ["AuthMutation"]
