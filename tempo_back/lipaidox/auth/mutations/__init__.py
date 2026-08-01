import strawberry
from .user_mutation import UserMutation
from .email_mutation import EmailMutation
from .phone_mutation import PhoneMutation
from .password_mutation import PasswordMutation

@strawberry.type
class AuthMutation(UserMutation, EmailMutation, PhoneMutation, PasswordMutation):
    pass

__all__ = ["AuthMutation"]
