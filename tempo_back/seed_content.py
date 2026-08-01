import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lipaidox_backend.settings')
django.setup()

from lipaidox.content.models import (
    Content, ContentSeries, ContentMedia, 
    ContentAccessRule, ContentStatus, ContentFormat, ContentAccessType, MediaRole
)
from lipaidox.creator_profile.models import CreatorProfile
from multitenant.models import Tenant

def seed():
    # Clear existing to avoid unique constraint issues with 1 profile
    Content.objects.all().delete()
    ContentSeries.objects.all().delete()

    profile = CreatorProfile.objects.first()
    if not profile:
        print("No CreatorProfile found.")
        return

    tenant = Tenant.objects.first()

    # 1. Create a Series
    series = ContentSeries.objects.create(
        creator=profile,
        tenant=tenant,
        title="Pro Video Masterclass",
        description="Techniques for high-engagement video content."
    )

    # 2. Create Content (Single Video)
    content = Content.objects.create(
        creator=profile,
        tenant=tenant,
        series=series,
        title="Lesson 1: Lighting Setup",
        description="The three-point lighting system explained.",
        content_format=ContentFormat.SINGLE_VIDEO, # Simplified format
        access_type=ContentAccessType.ONE_TIME,
        one_time_price=9.99,
        status=ContentStatus.PUBLISHED,
        is_continuous=True,
        episode_number=1,
        categories=["tutorial", "video"],
        allow_download=True
    )

    # 3. Add Media with Roles
    # A. MAIN VIDEO
    ContentMedia.objects.create(
        content=content,
        media_type='video',
        media_role=MediaRole.MAIN,
        file_url='https://storage.lipaidox.com/videos/lighting_main.mp4',
        file_name='lighting_main.mp4'
    )
    
    # B. THUMBNAIL
    ContentMedia.objects.create(
        content=content,
        media_type='image',
        media_role=MediaRole.THUMBNAIL,
        file_url='https://storage.lipaidox.com/thumbs/lighting_thumb.jpg',
        file_name='lighting_thumb.jpg'
    )

    # C. SLIDESHOW IMAGES (The "Gallery")
    ContentMedia.objects.create(
        content=content,
        media_type='image',
        media_role=MediaRole.SLIDESHOW_IMAGE,
        file_url='https://storage.lipaidox.com/slides/bts_1.jpg',
        sort_order=1,
        slide_topic="Behind the scenes: Gear setup",
        is_preview_slide=True
    )
    
    ContentMedia.objects.create(
        content=content,
        media_type='image',
        media_role=MediaRole.SLIDESHOW_IMAGE,
        file_url='https://storage.lipaidox.com/slides/bts_2.jpg',
        sort_order=2,
        slide_topic="Camera settings overview",
        is_preview_slide=False
    )

    # 4. Access Rule
    ContentAccessRule.objects.create(content=content, allow_download=True)

    print(f"✅ Re-seeded Content: '{content.title}' with 1 Video, 1 Thumb, and 2 Slideshow images.")

if __name__ == "__main__":
    seed()
