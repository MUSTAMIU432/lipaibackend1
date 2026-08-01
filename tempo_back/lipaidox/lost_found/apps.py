from django.apps import AppConfig


class LostFoundConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lipaidox.lost_found'
    verbose_name = 'Lost & Found'
    
    def ready(self):
        """Initialize AI services when app is ready"""
        # AI services will be initialized after they are created
        pass
