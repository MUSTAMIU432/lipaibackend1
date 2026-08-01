import strawberry
from typing import Optional

@strawberry.type
class UsernameQuery:
    @strawberry.field
    def check_username_availability(self, info: strawberry.types.Info, username: str) -> bool:
        """Check if a username is available for use"""
        print(f"USERNAME CHECK: {username}")
        
        user = info.context.request.user
        if not user.is_authenticated:
            print("USER NOT AUTHENTICATED")
            return False
        
        print(f"USER: {user.username}")
        
        # Direct database query
        from lipaidox.creator_profile.models import UsernameHistory
        
        # Check if username exists and is not available
        exists = UsernameHistory.objects.filter(
            username=username,
            tenant=user.tenant,
            is_available=False
        ).exclude(user=user).exists()
        
        print(f"USERNAME {username} exists: {exists}")
        
        # Return opposite - available if doesn't exist
        result = not exists
        print(f"FINAL RESULT: {result}")
        
        return result
