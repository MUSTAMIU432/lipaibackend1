"""
URL patterns for Lost & Found Module
REST API endpoints for all 6 AI features
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import views
from .views import (
    create_lost_found_item,
    analyze_image_with_ai,
    get_lost_found_items,
    get_lost_found_item_detail,
    search_similar_items,
    vote_on_item,
    report_item,
    get_item_consensus,
    get_user_voting_history,
    get_trending_items,
    moderate_report,
    compare_prices,
    get_service_health,
    get_statistics,
    update_item_status,
    delete_item,
    discover_analyze,
    discover_similar_place,
)

app_name = 'lost_found'

urlpatterns = [
    # === Core Lost & Found Operations ===
    path('items/', get_lost_found_items, name='get_lost_found_items'),
    path('items/create/', create_lost_found_item, name='create_lost_found_item'),
    path('items/<uuid:item_id>/', get_lost_found_item_detail, name='get_lost_found_item_detail'),
    path('items/<uuid:item_id>/update-status/', update_item_status, name='update_item_status'),
    path('items/<uuid:item_id>/delete/', delete_item, name='delete_item'),
    
    # === AI Analysis Endpoints ===
    path('analyze/', analyze_image_with_ai, name='analyze_image_with_ai'),
    path('search/similar/', search_similar_items, name='search_similar_items'),
    path('compare-prices/', compare_prices, name='compare_prices'),

    # === Discover page (frontend /discover) ===
    path('discover/analyze/',       discover_analyze,       name='discover_analyze'),
    path('discover/similar-place/', discover_similar_place, name='discover_similar_place'),
    
    # === Community & Voting ===
    path('items/<uuid:item_id>/vote/', vote_on_item, name='vote_on_item'),
    path('items/<uuid:item_id>/report/', report_item, name='report_item'),
    path('items/<uuid:item_id>/consensus/', get_item_consensus, name='get_item_consensus'),
    path('user/voting-history/', get_user_voting_history, name='get_user_voting_history'),
    path('trending/', get_trending_items, name='get_trending_items'),
    path('reports/<uuid:report_id>/moderate/', moderate_report, name='moderate_report'),
    
    # === System & Monitoring ===
    path('system/health/', get_service_health, name='get_service_health'),
    path('system/statistics/', get_statistics, name='get_statistics'),
    
    # === Legacy/Individual Feature Endpoints ===
    # These provide direct access to individual AI features
    path('features/visual-search/', analyze_image_with_ai, name='visual_search_feature'),
    path('features/ai-detection/', analyze_image_with_ai, name='ai_detection_feature'),
    path('features/qr-scanner/', analyze_image_with_ai, name='qr_scanner_feature'),
    path('features/price-compare/', compare_prices, name='price_compare_feature'),
    path('features/deepfake/', analyze_image_with_ai, name='deepfake_feature'),
    path('features/community/', get_item_consensus, name='community_feature'),
]

# API Versioning
api_v1_patterns = [
    path('api/v1/lost-found/', include(urlpatterns)),
]

# Optional: Router for future DRF ViewSets
router = DefaultRouter()
# router.register(r'items', LostFoundItemViewSet)
# router.register(r'votes', VoteViewSet)
# router.register(r'reports', ReportViewSet)
