import strawberry
from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from ..models import (
    LiveStream, LiveStreamViewer, LiveStreamChatMessage, LiveStreamCreditTransaction,
    LiveStreamStatus, LiveStreamAccessType, ViewerStatus, ChatMessageStatus,
    LiveStreamMedia,
)
from ..schema.live_streaming_schema import (
    LiveStreamType, LiveStreamViewerType, LiveStreamChatMessageType,
    LiveStreamCreditTransactionType, LiveStreamStatisticsType, LiveStreamMediaType,
    CreateLiveStreamInput, UpdateLiveStreamInput, StartStreamInput,
    SendChatMessageInput, JoinStreamInput, LeaveStreamInput
)
from lipaidox.auth.permissions import UserRoles


def _stream_qs_with_creator():
    """Base queryset that eagerly loads creator profile to avoid N+1."""
    return LiveStream.objects.select_related("creator", "creator__user")


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def require_creator(user):
    """Check if user is a creator"""
    if user.role != UserRoles.CREATOR:
        raise Exception("Creator access required")
    return True


# ── Aggregated creator-dashboard analytics types ────────────────────────────────
@strawberry.type
class LiveSupporterType:
    username: str
    display_name: str
    avatar_url: Optional[str]
    total_tips: float
    total_credits: int
    is_subscriber: bool


@strawberry.type
class AudienceCountryType:
    country: str
    viewers: int
    pct: int


@strawberry.type
class CreatorLiveAnalyticsType:
    top_supporters: List[LiveSupporterType]
    audience_by_country: List[AudienceCountryType]
    subscribers_total: int
    subscribers_new_this_week: int
    followers_total: int
    followers_new_this_week: int


@strawberry.type
class LiveStreamingQuery:
    # Public Queries
    @strawberry.field
    def live_streams(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        category: Optional[str] = None,
        creatorId: Optional[strawberry.ID] = None,
        limit: int = 50
    ) -> List[LiveStreamType]:
        """Get live streams with optional filters"""
        queryset = _stream_qs_with_creator()

        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category=category)
        if creatorId:
            queryset = queryset.filter(creator_id=creatorId)

        return [LiveStreamType.from_model(stream) for stream in queryset.order_by('-created_at')[:limit]]

    @strawberry.field
    def live_stream_by_id(
        self,
        info: strawberry.types.Info,
        streamId: strawberry.ID
    ) -> Optional[LiveStreamType]:
        """Get specific live stream by ID"""
        try:
            stream = _stream_qs_with_creator().get(id=streamId)
            return LiveStreamType.from_model(stream)
        except LiveStream.DoesNotExist:
            return None

    @strawberry.field
    def live_streams_now(self, info: strawberry.types.Info, limit: int = 50) -> List[LiveStreamType]:
        """Get currently live streams ordered by viewer count (hot first)."""
        # Also clean up zombie SCHEDULED streams that have been sitting for > 2 hours
        # without ever being started — prevents them piling up and polluting the DB.
        stale_cutoff = timezone.now() - timedelta(hours=2)
        LiveStream.objects.filter(
            status=LiveStreamStatus.SCHEDULED,
            created_at__lt=stale_cutoff,
            started_at__isnull=True,
        ).update(status=LiveStreamStatus.CANCELLED)

        streams = (
            _stream_qs_with_creator()
            .filter(status=LiveStreamStatus.LIVE)
            .order_by('-current_viewer_count', '-started_at')
            [:limit]
        )
        return [LiveStreamType.from_model(stream) for stream in streams]

    @strawberry.field
    def recently_ended_streams(
        self,
        info: strawberry.types.Info,
        limit: int = 20,
        hours: int = 24,
    ) -> List[LiveStreamType]:
        """Get streams that ended within the last N hours — used as fallback discovery content."""
        cutoff = timezone.now() - timedelta(hours=hours)
        streams = (
            _stream_qs_with_creator()
            .filter(status=LiveStreamStatus.ENDED, ended_at__gte=cutoff)
            .order_by('-ended_at')
            [:limit]
        )
        return [LiveStreamType.from_model(stream) for stream in streams]

    @strawberry.field
    def scheduled_streams(
        self,
        info: strawberry.types.Info,
        limit: int = 50
    ) -> List[LiveStreamType]:
        """Get upcoming scheduled streams"""
        streams = (
            _stream_qs_with_creator()
            .filter(
                status=LiveStreamStatus.SCHEDULED,
                scheduled_at__gte=timezone.now(),
            )
            .order_by('scheduled_at')
            [:limit]
        )
        return [LiveStreamType.from_model(stream) for stream in streams]
    
    # Creator Queries
    @strawberry.field
    def my_live_streams(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[LiveStreamType]:
        """Get creator's live streams"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
            queryset = _stream_qs_with_creator().filter(creator=profile)
            if status:
                queryset = queryset.filter(status=status)
            return [LiveStreamType.from_model(stream) for stream in queryset.order_by('-created_at')[:limit]]
        except CreatorProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def my_live_stream_statistics(self, info: strawberry.types.Info) -> LiveStreamStatisticsType:
        """Get live streaming statistics for creator"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        from django.db.models import Sum, Count
        
        try:
            profile = CreatorProfile.objects.get(user=user)
            streams = LiveStream.objects.filter(creator=profile)
            
            total = streams.count()
            live = streams.filter(status=LiveStreamStatus.LIVE).count()
            scheduled = streams.filter(status=LiveStreamStatus.SCHEDULED).count()
            ended = streams.filter(status=LiveStreamStatus.ENDED).count()
            
            total_viewers = streams.aggregate(total=Sum('total_viewer_count'))['total'] or 0
            total_revenue = streams.aggregate(total=Sum('total_revenue'))['total'] or 0
            total_tips = streams.aggregate(total=Sum('total_tips_amount'))['total'] or 0
            total_credits = streams.aggregate(total=Sum('total_credits_received'))['total'] or 0
            
            return LiveStreamStatisticsType(
                totalStreams=total,
                liveStreams=live,
                scheduledStreams=scheduled,
                endedStreams=ended,
                totalViewers=total_viewers,
                totalRevenue=total_revenue,
                totalTips=total_tips,
                totalCredits=total_credits
            )
        except CreatorProfile.DoesNotExist:
            return LiveStreamStatisticsType(
                totalStreams=0,
                liveStreams=0,
                scheduledStreams=0,
                endedStreams=0,
                totalViewers=0,
                totalRevenue=0,
                totalTips=0,
                totalCredits=0
            )

    @strawberry.field
    def my_creator_live_analytics(self, info: strawberry.types.Info) -> CreatorLiveAnalyticsType:
        """Aggregated creator-dashboard analytics — top supporters, audience by
        country and subscriber/follower totals with 7-day growth. Every figure is
        computed from real rows (LiveStreamViewer / MembershipSubscription / Follow)."""
        user = require_auth(info)
        require_creator(user)

        from lipaidox.creator_profile.models import (
            CreatorProfile, MembershipSubscription, MembershipStatus, Follow,
        )
        from django.db.models import Sum, Count

        empty = CreatorLiveAnalyticsType(
            top_supporters=[], audience_by_country=[],
            subscribers_total=0, subscribers_new_this_week=0,
            followers_total=0, followers_new_this_week=0,
        )
        try:
            profile = CreatorProfile.objects.get(user=user)
        except CreatorProfile.DoesNotExist:
            return empty

        week_ago = timezone.now() - timedelta(days=7)
        viewers = LiveStreamViewer.objects.filter(live_stream__creator=profile)

        # Active subscribers (also drives the is_subscriber flag on supporters)
        sub_qs = MembershipSubscription.objects.filter(
            target=profile, status=MembershipStatus.ACTIVE
        )
        subscriber_ids = set(sub_qs.values_list("subscriber_id", flat=True))

        # ── Top supporters — per fan, ranked by tips then credits ──
        supporter_rows = (
            viewers.values("fan_id", "fan__username", "fan__profile__profile_photo_url")
            .annotate(tips=Sum("tips_sent"), credits=Sum("credits_sent"))
            .order_by("-tips", "-credits")[:5]
        )
        top_supporters = []
        for r in supporter_rows:
            tips = float(r["tips"] or 0)
            credits = int(r["credits"] or 0)
            if tips <= 0 and credits <= 0:
                continue
            uname = r["fan__username"] or "fan"
            top_supporters.append(LiveSupporterType(
                username=uname,
                display_name=uname,
                avatar_url=r["fan__profile__profile_photo_url"],
                total_tips=tips,
                total_credits=credits,
                is_subscriber=r["fan_id"] in subscriber_ids,
            ))

        # ── Audience by country — distinct fans grouped by their profile country ──
        country_rows = (
            viewers.values("fan__profile__country_of_residence")
            .annotate(c=Count("fan_id", distinct=True))
            .order_by("-c")
        )
        total_fans = sum(row["c"] for row in country_rows) or 1
        audience = [
            AudienceCountryType(
                country=row["fan__profile__country_of_residence"] or "Unknown",
                viewers=row["c"],
                pct=round(row["c"] / total_fans * 100),
            )
            for row in country_rows[:6]
        ]

        # ── Subscribers & followers (totals + 7-day growth) ──
        follows = Follow.objects.filter(followed=user)
        return CreatorLiveAnalyticsType(
            top_supporters=top_supporters,
            audience_by_country=audience,
            subscribers_total=sub_qs.count(),
            subscribers_new_this_week=sub_qs.filter(created_at__gte=week_ago).count(),
            followers_total=follows.count(),
            followers_new_this_week=follows.filter(created_at__gte=week_ago).count(),
        )

    @strawberry.field
    def live_stream_viewers(
        self,
        info: strawberry.types.Info,
        streamId: strawberry.ID,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[LiveStreamViewerType]:
        """Get viewers for a live stream (creator or admin only)"""
        user = require_auth(info)
        
        try:
            stream = LiveStream.objects.get(id=streamId)
            # Only creator or admin can see viewers
            if user.role not in [UserRoles.ADMIN, 'superadmin'] and stream.creator.user != user:
                return []
            
            queryset = LiveStreamViewer.objects.filter(live_stream=stream)
            if status:
                queryset = queryset.filter(status=status)
            
            return [LiveStreamViewerType.from_model(viewer) for viewer in queryset.order_by('-joined_at')[:limit]]
        except LiveStream.DoesNotExist:
            return []
    
    @strawberry.field
    def live_stream_chat_messages(
        self,
        info: strawberry.types.Info,
        streamId: strawberry.ID,
        limit: int = 100
    ) -> List[LiveStreamChatMessageType]:
        """Get chat messages for a live stream — public read, no auth required."""
        try:
            stream = LiveStream.objects.get(id=streamId)
            messages = LiveStreamChatMessage.objects.filter(
                live_stream=stream,
                status=ChatMessageStatus.VISIBLE
            ).order_by('sent_at')[:limit]
            return [LiveStreamChatMessageType.from_model(msg) for msg in messages]
        except LiveStream.DoesNotExist:
            return []
    
    @strawberry.field
    def my_live_stream_view_history(
        self,
        info: strawberry.types.Info,
        limit: int = 50
    ) -> List[LiveStreamViewerType]:
        """Get current user's live stream viewing history"""
        user = require_auth(info)
        
        viewers = LiveStreamViewer.objects.filter(fan=user).order_by('-joined_at')[:limit]
        return [LiveStreamViewerType.from_model(viewer) for viewer in viewers]
    
    # Admin Queries
    @strawberry.field
    def all_live_streams(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        creatorId: Optional[strawberry.ID] = None,
        limit: int = 100
    ) -> List[LiveStreamType]:
        """Get all live streams (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return []
        
        queryset = _stream_qs_with_creator()
        if status:
            queryset = queryset.filter(status=status)
        if creatorId:
            queryset = queryset.filter(creator_id=creatorId)

        return [LiveStreamType.from_model(stream) for stream in queryset.order_by('-created_at')[:limit]]
    
    @strawberry.field
    def live_stream_credit_transactions(
        self,
        info: strawberry.types.Info,
        streamId: strawberry.ID,
        limit: int = 100
    ) -> List[LiveStreamCreditTransactionType]:
        """Get credit transactions for a live stream (admin or creator)"""
        user = require_auth(info)
        
        try:
            stream = LiveStream.objects.get(id=streamId)
            # Only creator or admin can see transactions
            if user.role not in [UserRoles.ADMIN, 'superadmin'] and stream.creator.user != user:
                return []
            
            transactions = LiveStreamCreditTransaction.objects.filter(live_stream=stream).order_by('-received_at')[:limit]
            return [LiveStreamCreditTransactionType.from_model(tx) for tx in transactions]
        except LiveStream.DoesNotExist:
            return []


    @strawberry.field
    def live_stream_media(
        self,
        info: strawberry.types.Info,
        stream_id: strawberry.ID,
    ) -> List[LiveStreamMediaType]:
        """Get all media files uploaded for a stream session."""
        user = require_auth(info)
        try:
            stream = LiveStream.objects.get(id=stream_id)
        except LiveStream.DoesNotExist:
            return []
        # Creator and authenticated viewers can list media
        media = LiveStreamMedia.objects.filter(live_stream=stream).order_by('created_at')
        return [LiveStreamMediaType.from_model(m) for m in media]
