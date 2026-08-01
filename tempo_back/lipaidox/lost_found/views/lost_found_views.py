"""
Django Views for Lost & Found Module
REST API endpoints for all 6 AI features
"""

import json
import uuid
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.paginator import Paginator
from django.db.models import Q, Count
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

# Import AI services
from ..services import get_ai_service_manager
from ..models.lost_found import LostFoundItem, ItemImage, Vote, Report, ProductCache

User = get_user_model()


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def create_lost_found_item(request):
    """
    Create new Lost & Found item with full AI processing
    """
    try:
        # Validate required fields
        if 'image' not in request.FILES:
            return Response(
                {"error": "Image file is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if 'title' not in request.data:
            return Response(
                {"error": "Title is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract item data
        item_data = {
            "title": request.data['title'],
            "description": request.data.get('description', ''),
            "category": request.data.get('category', ''),
            "status": request.data.get('status', 'lost'),
            "location_lat": request.data.get('location_lat'),
            "location_lng": request.data.get('location_lng'),
            "location_address": request.data.get('location_address', ''),
            "location_description": request.data.get('location_description', ''),
            "tags": json.loads(request.data.get('tags', '[]')),
            "priority": int(request.data.get('priority', 1)),
            "is_featured": request.data.get('is_featured', 'false').lower() == 'true'
        }
        
        # Get AI service manager
        ai_manager = get_ai_service_manager()
        
        # Process item with all AI services
        result = ai_manager.create_lost_found_item(
            request.FILES['image'],
            item_data,
            str(request.user.id)
        )
        
        if result["status"] == "success":
            return Response(result, status=status.HTTP_201_CREATED)
        else:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to create Lost & Found item"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def analyze_image_with_ai(request):
    """
    Analyze image with specific AI service or all services
    """
    try:
        if 'image' not in request.FILES:
            return Response(
                {"error": "Image file is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get service name (optional)
        service_name = request.data.get('service_name', None)
        
        # Get AI service manager
        ai_manager = get_ai_service_manager()
        
        if service_name:
            # Process with specific service
            result = ai_manager.process_service_specific(
                request.FILES['image'],
                service_name,
                request.data.dict()
            )
        else:
            # Process with all services
            item_data = {
                "title": request.data.get('title', ''),
                "category": request.data.get('category', '')
            }
            result = ai_manager.process_item_complete(
                request.FILES['image'],
                item_data,
                request.data.get('category')
            )
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to analyze image"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_lost_found_items(request):
    """
    Get list of Lost & Found items with filtering and pagination
    """
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        status_filter = request.GET.get('status', None)
        category_filter = request.GET.get('category', None)
        search_query = request.GET.get('search', None)
        sort_by = request.GET.get('sort_by', '-created_at')
        
        # Build query
        queryset = LostFoundItem.objects.all()
        
        # Apply filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Apply sorting
        if sort_by.startswith('-'):
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by(sort_by)
        
        # Paginate
        paginator = Paginator(queryset, page_size)
        items_page = paginator.get_page(page)
        
        # Serialize items
        items_data = []
        for item in items_page:
            items_data.append({
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "category": item.category,
                "status": item.status,
                "location_address": item.location_address,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "image_count": item.image_count,
                "view_count": item.view_count,
                "is_featured": item.is_featured,
                "priority": item.priority,
                "tags": item.tags,
                "community_consensus": item.community_consensus
            })
        
        return Response({
            "items": items_data,
            "pagination": {
                "current_page": page,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "page_size": page_size,
                "has_next": items_page.has_next(),
                "has_previous": items_page.has_previous()
            }
        })
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to get Lost & Found items"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_lost_found_item_detail(request, item_id):
    """
    Get detailed information about a specific Lost & Found item
    """
    try:
        item = LostFoundItem.objects.get(id=item_id)
        
        # Increment view count
        item.view_count += 1
        item.save(update_fields=['view_count'])
        
        # Get images
        images = []
        for img in item.images.all():
            images.append({
                "id": str(img.id),
                "original_filename": img.original_filename,
                "file_path": img.file_path,
                "file_size": img.file_size,
                "content_type": img.content_type,
                "width": img.width,
                "height": img.height,
                "ai_class": img.ai_class,
                "confidence_score": float(img.confidence_score) if img.confidence_score else None,
                "created_at": img.created_at.isoformat()
            })
        
        # Get matches
        matches = []
        for match in item.matches_a.all().order_by('-similarity_score')[:10]:
            matches.append({
                "id": str(match.id),
                "matched_item_id": str(match.item_b.id),
                "matched_item_title": match.item_b.title,
                "match_type": match.match_type,
                "similarity_score": float(match.similarity_score),
                "visual_score": float(match.visual_score) if match.visual_score else None,
                "is_confirmed": match.is_confirmed,
                "created_at": match.created_at.isoformat()
            })
        
        return Response({
            "item": {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "category": item.category,
                "status": item.status,
                "reporter": {
                    "id": str(item.reporter.id),
                    "username": item.reporter.username
                } if item.reporter else None,
                "claimer": {
                    "id": str(item.claimer.id),
                    "username": item.claimer.username
                } if item.claimer else None,
                "location": {
                    "lat": float(item.location_lat) if item.location_lat else None,
                    "lng": float(item.location_lng) if item.location_lng else None,
                    "address": item.location_address,
                    "description": item.location_description
                },
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "reported_date": item.reported_date.isoformat() if item.reported_date else None,
                "claimed_date": item.claimed_date.isoformat() if item.claimed_date else None,
                "tags": item.tags,
                "priority": item.priority,
                "is_featured": item.is_featured,
                "view_count": item.view_count,
                "images": images,
                "matches": matches,
                "ai_results": {
                    "visual_search": item.visual_search_result,
                    "ai_detection": item.ai_detection_result,
                    "qr_data": item.qr_data,
                    "price_comparison": item.price_comparison,
                    "deepfake_result": item.deepfake_result,
                    "community_consensus": item.community_consensus
                }
            }
        })
    
    except LostFoundItem.DoesNotExist:
        return Response(
            {"error": "Item not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to get item details"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def search_similar_items(request):
    """
    Search for similar items using visual search
    """
    try:
        if 'image' not in request.FILES:
            return Response(
                {"error": "Image file is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        threshold = float(request.data.get('threshold', 0.5))
        
        # Get AI service manager
        ai_manager = get_ai_service_manager()
        
        # Search for similar items
        result = ai_manager.search_similar_items(request.FILES['image'], threshold)
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to search similar items"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vote_on_item(request, item_id):
    """
    Vote on a Lost & Found item
    """
    try:
        vote_type = request.data.get('vote_type')
        comment = request.data.get('comment', '')
        weight = request.data.get('weight')
        
        if not vote_type:
            return Response(
                {"error": "Vote type is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get community service
        community_service = get_ai_service_manager().community_service
        
        # Cast vote
        result = community_service.vote_on_item(
            item_id,
            str(request.user.id),
            vote_type,
            comment,
            Decimal(weight) if weight else None
        )
        
        if result["status"] == "success":
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to vote on item"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_item(request, item_id):
    """
    Report a Lost & Found item
    """
    try:
        report_type = request.data.get('report_type')
        reason = request.data.get('reason', '')
        
        if not report_type:
            return Response(
                {"error": "Report type is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reason:
            return Response(
                {"error": "Reason is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get community service
        community_service = get_ai_service_manager().community_service
        
        # Submit report
        result = community_service.report_item(
            item_id,
            str(request.user.id),
            report_type,
            reason
        )
        
        if result["status"] == "success":
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to report item"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_item_consensus(request, item_id):
    """
    Get consensus and voting statistics for an item
    """
    try:
        # Get community service
        community_service = get_ai_service_manager().community_service
        
        # Get consensus
        result = community_service.get_item_consensus(item_id)
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to get item consensus"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_voting_history(request):
    """
    Get current user's voting history
    """
    try:
        limit = int(request.GET.get('limit', 50))
        
        # Get community service
        community_service = get_ai_service_manager().community_service
        
        # Get voting history
        result = community_service.get_user_voting_history(str(request.user.id), limit)
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to get voting history"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_trending_items(request):
    """
    Get trending Lost & Found items
    """
    try:
        time_period = int(request.GET.get('time_period_hours', 24))
        limit = int(request.GET.get('limit', 10))
        
        # Get community service
        community_service = get_ai_service_manager().community_service
        
        # Get trending items
        result = community_service.get_trending_items(time_period, limit)
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to get trending items"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def moderate_report(request, report_id):
    """
    Moderate a reported item (admin/moderator only)
    """
    try:
        action = request.data.get('action')
        note = request.data.get('note', '')
        
        if not action:
            return Response(
                {"error": "Action is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get community service
        community_service = get_ai_service_manager().community_service
        
        # Moderate report
        result = community_service.moderate_reports(
            report_id,
            str(request.user.id),
            action,
            note
        )
        
        if result["status"] == "success":
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to moderate report"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def compare_prices(request):
    """
    Compare prices for a product
    """
    try:
        product_name = request.GET.get('product_name')
        use_cache = request.GET.get('use_cache', 'true').lower() == 'true'
        
        if not product_name:
            return Response(
                {"error": "Product name is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get price compare service
        price_service = get_ai_service_manager().price_compare_service
        
        # Compare prices
        result = price_service.compare_prices(product_name, use_cache)
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to compare prices"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_service_health(request):
    """
    Get health status of all AI services
    """
    try:
        # Get AI service manager
        ai_manager = get_ai_service_manager()
        
        # Get service health
        result = ai_manager.get_service_health()
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to get service health"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_statistics(request):
    """
    Get comprehensive statistics for all services
    """
    try:
        # Get AI service manager
        ai_manager = get_ai_service_manager()
        
        # Get statistics
        result = ai_manager.get_statistics()
        
        return Response(result)
    
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to get statistics"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_item_status(request, item_id):
    """
    Update the status of a Lost & Found item
    """
    try:
        new_status = request.data.get('status')
        
        if not new_status:
            return Response(
                {"error": "Status is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate status
        valid_statuses = [choice[0] for choice in LostFoundItem.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {"error": f"Invalid status. Must be one of: {valid_statuses}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get and update item
        item = LostFoundItem.objects.get(id=item_id)
        
        # Check permissions (only reporter or admin can update)
        if item.reporter != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        item.status = new_status
        
        # Set claimer if status is 'claimed'
        if new_status == 'claimed' and not item.claimer:
            item.claimer = request.user
            item.claimed_date = timezone.now()
        
        item.save()
        
        return Response({
            "status": "success",
            "message": f"Item status updated to {new_status}",
            "item_id": str(item.id),
            "new_status": item.status
        })
    
    except LostFoundItem.DoesNotExist:
        return Response(
            {"error": "Item not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to update item status"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_item(request, item_id):
    """
    Delete a Lost & Found item
    """
    try:
        # Get item
        item = LostFoundItem.objects.get(id=item_id)
        
        # Check permissions (only reporter or admin can delete)
        if item.reporter != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete item (this will also delete related images, votes, etc.)
        item.delete()
        
        return Response({
            "status": "success",
            "message": "Item deleted successfully",
            "item_id": item_id
        })
    
    except LostFoundItem.DoesNotExist:
        return Response(
            {"error": "Item not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e), "message": "Failed to delete item"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
