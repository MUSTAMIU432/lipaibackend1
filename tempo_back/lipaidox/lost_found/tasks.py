"""
Celery Tasks for Lost & Found Module
Async processing for heavy AI operations
"""

import os
import json
import time
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.contrib.auth import get_user_model

# Import AI services
from ..services import get_ai_service_manager
from ..models.lost_found import LostFoundItem, ItemImage, ProductCache

User = get_user_model()


@shared_task(bind=True, max_retries=3)
def process_ai_features_async(self, image_id: str, item_id: str, service_names: list = None):
    """
    Process AI features asynchronously for an image
    """
    try:
        # Get image and item
        image = ItemImage.objects.get(id=image_id)
        item = LostFoundItem.objects.get(id=item_id)
        
        # Get image file
        image_file = None
        if image.file_path and default_storage.exists(image.file_path):
            image_file = default_storage.open(image.file_path)
        
        if not image_file:
            raise Exception("Image file not found")
        
        # Get AI service manager
        ai_manager = get_ai_service_manager()
        
        # Process specific services or all
        if service_names:
            results = {}
            for service_name in service_names:
                result = ai_manager.process_service_specific(
                    image_file, service_name, {"title": item.title, "category": item.category}
                )
                results[service_name] = result
        else:
            # Process all services
            item_data = {
                "title": item.title,
                "description": item.description,
                "category": item.category
            }
            full_result = ai_manager.process_item_complete(
                image_file, item_data, item.category
            )
            results = full_result.get("services", {})
        
        # Update item with results
        if 'visual_search' in results:
            item.visual_search_result = results['visual_search']
        
        if 'ai_detection' in results:
            item.ai_detection_result = results['ai_detection']
        
        if 'qr_scanner' in results:
            item.qr_data = results['qr_scanner']
        
        if 'price_compare' in results:
            item.price_comparison = results['price_compare']
        
        if 'deepfake' in results:
            item.deepfake_result = results['deepfake']
        
        item.save(update_fields=[
            'visual_search_result',
            'ai_detection_result', 
            'qr_data',
            'price_comparison',
            'deepfake_result'
        ])
        
        # Update image record
        if 'visual_search' in results:
            visual_result = results['visual_search']
            if visual_result.get("embedding"):
                image.embedding = visual_result["embedding"]
            if visual_result.get("detected_class"):
                image.ai_class = visual_result["detected_class"]
            if visual_result.get("confidence"):
                image.confidence_score = visual_result["confidence"]
        
        image.is_processed = True
        image.save(update_fields=['embedding', 'ai_class', 'confidence_score', 'is_processed'])
        
        # Update visual search index
        if 'visual_search' in results and results['visual_search'].get("embedding"):
            ai_manager.visual_search_service.add_to_index(
                results['visual_search']["embedding"],
                str(image.id)
            )
            ai_manager.visual_search_service.update_item_matches(item)
        
        return {
            "status": "success",
            "image_id": image_id,
            "item_id": item_id,
            "processed_services": list(results.keys()),
            "processing_time": time.time()
        }
        
    except Exception as e:
        # Update image with error
        try:
            image = ItemImage.objects.get(id=image_id)
            image.processing_error = str(e)
            image.save(update_fields=['processing_error'])
        except:
            pass
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            "status": "error",
            "image_id": image_id,
            "item_id": item_id,
            "error": str(e),
            "retries": self.request.retries
        }


@shared_task(bind=True, max_retries=2)
def scrape_prices_async(self, product_name: str, item_id: str = None):
    """
    Scrape prices asynchronously for a product
    """
    try:
        # Get price compare service
        ai_manager = get_ai_service_manager()
        price_service = ai_manager.price_compare_service
        
        # Scrape prices
        result = price_service.compare_prices(product_name, use_cache=False)
        
        # Update item if provided
        if item_id:
            try:
                item = LostFoundItem.objects.get(id=item_id)
                item.price_comparison = result
                item.save(update_fields=['price_comparison'])
            except LostFoundItem.DoesNotExist:
                pass
        
        return {
            "status": "success",
            "product_name": product_name,
            "item_id": item_id,
            "price_data": result,
            "scraped_at": timezone.now().isoformat()
        }
        
    except Exception as e:
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            "status": "error",
            "product_name": product_name,
            "item_id": item_id,
            "error": str(e),
            "retries": self.request.retries
        }


@shared_task(bind=True, max_retries=2)
def update_faiss_index_async(self):
    """
    Update Faiss index with all existing embeddings
    """
    try:
        # Get visual search service
        ai_manager = get_ai_service_manager()
        visual_service = ai_manager.visual_search_service
        
        # Get all images with embeddings
        images = ItemImage.objects.filter(
            embedding__isnull=False,
            is_processed=True
        )
        
        # Rebuild index
        embeddings = []
        image_ids = []
        
        for image in images:
            if image.embedding:
                embedding = image.embedding
                if isinstance(embedding, list):
                    import numpy as np
                    embedding = np.array(embedding, dtype='float32')
                embeddings.append(embedding)
                image_ids.append(str(image.id))
        
        if embeddings:
            import numpy as np
            embeddings_matrix = np.vstack(embeddings)
            
            # Reset and rebuild index
            visual_service.faiss_index.reset()
            visual_service.faiss_index.add(embeddings_matrix)
            
            # Save index
            index_path = os.path.join(settings.MEDIA_ROOT, 'faiss', 'visual_search.index')
            os.makedirs(os.path.dirname(index_path), exist_ok=True)
            import faiss
            faiss.write_index(visual_service.faiss_index, index_path)
        
        return {
            "status": "success",
            "total_images": len(images),
            "indexed_images": len(embeddings),
            "updated_at": timezone.now().isoformat()
        }
        
    except Exception as e:
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            "status": "error",
            "error": str(e),
            "retries": self.request.retries
        }


@shared_task(bind=True, max_retries=1)
def cleanup_old_cache_async(self, days_old: int = 30):
    """
    Clean up old price cache entries
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        # Delete old cache entries
        deleted_count = ProductCache.objects.filter(
            last_scraped__lt=cutoff_date,
            is_active=False
        ).delete()[0]
        
        # Archive old but still active entries
        archived_count = ProductCache.objects.filter(
            last_scraped__lt=cutoff_date,
            is_active=True
        ).update(is_active=False)
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "archived_count": archived_count,
            "cutoff_date": cutoff_date.isoformat(),
            "cleaned_at": timezone.now().isoformat()
        }
        
    except Exception as e:
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            "status": "error",
            "error": str(e),
            "retries": self.request.retries
        }


@shared_task(bind=True, max_retries=1)
def generate_item_matches_async(self, item_id: str):
    """
    Generate matches for a specific item
    """
    try:
        # Get item and its main image
        item = LostFoundItem.objects.get(id=item_id)
        main_image = item.images.first()
        
        if not main_image or not main_image.embedding:
            return {
                "status": "skipped",
                "item_id": item_id,
                "reason": "No image or embedding found"
            }
        
        # Get visual search service
        ai_manager = get_ai_service_manager()
        visual_service = ai_manager.visual_search_service
        
        # Update matches
        visual_service.update_item_matches(item)
        
        return {
            "status": "success",
            "item_id": item_id,
            "image_id": str(main_image.id),
            "updated_at": timezone.now().isoformat()
        }
        
    except LostFoundItem.DoesNotExist:
        return {
            "status": "error",
            "item_id": item_id,
            "error": "Item not found"
        }
    except Exception as e:
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            "status": "error",
            "item_id": item_id,
            "error": str(e),
            "retries": self.request.retries
        }


@shared_task(bind=True, max_retries=1)
def send_notifications_async(self, notification_type: str, recipients: list, data: dict):
    """
    Send notifications to users asynchronously
    """
    try:
        sent_count = 0
        failed_count = 0
        
        for recipient_id in recipients:
            try:
                user = User.objects.get(id=recipient_id)
                
                # Here you would implement actual notification sending
                # e.g., email, push notification, SMS, etc.
                
                sent_count += 1
                
            except User.DoesNotExist:
                failed_count += 1
            except Exception as e:
                print(f"Failed to send notification to {recipient_id}: {e}")
                failed_count += 1
        
        return {
            "status": "success",
            "notification_type": notification_type,
            "total_recipients": len(recipients),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "sent_at": timezone.now().isoformat()
        }
        
    except Exception as e:
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            "status": "error",
            "notification_type": notification_type,
            "error": str(e),
            "retries": self.request.retries
        }


@shared_task(bind=True, max_retries=1)
def update_community_consensus_async(self, item_id: str):
    """
    Update community consensus for an item
    """
    try:
        # Get community service
        ai_manager = get_ai_service_manager()
        community_service = ai_manager.community_service
        
        # Update consensus
        community_service._update_item_consensus(
            LostFoundItem.objects.get(id=item_id)
        )
        
        return {
            "status": "success",
            "item_id": item_id,
            "updated_at": timezone.now().isoformat()
        }
        
    except LostFoundItem.DoesNotExist:
        return {
            "status": "error",
            "item_id": item_id,
            "error": "Item not found"
        }
    except Exception as e:
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            "status": "error",
            "item_id": item_id,
            "error": str(e),
            "retries": self.request.retries
        }


@shared_task
def health_check_async():
    """
    Periodic health check for all AI services
    """
    try:
        # Get AI service manager
        ai_manager = get_ai_service_manager()
        
        # Get health status
        health_status = ai_manager.get_service_health()
        
        # Log health status (you could send to monitoring service)
        print(f"AI Services Health Check: {health_status}")
        
        return {
            "status": "success",
            "health_check": health_status,
            "checked_at": timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "checked_at": timezone.now().isoformat()
        }


# Periodic task configuration (add to celery beat schedule)
CELERYBEAT_SCHEDULE = {
    'update-faiss-index': {
        'task': 'lipaidox.lost_found.tasks.update_faiss_index_async',
        'schedule': 3600.0,  # Every hour
    },
    'cleanup-old-cache': {
        'task': 'lipaidox.lost_found.tasks.cleanup_old_cache_async',
        'schedule': 86400.0,  # Every day
        'args': (30,),  # Clean cache older than 30 days
    },
    'health-check': {
        'task': 'lipaidox.lost_found.tasks.health_check_async',
        'schedule': 300.0,  # Every 5 minutes
    },
}
