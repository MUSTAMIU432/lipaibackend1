import dataclasses
import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..models import (
    LiveStream, LiveStreamViewer, LiveStreamChatMessage, LiveStreamCreditTransaction,
    LiveStreamStatus, LiveStreamAccessType, ViewerStatus, ChatMessageStatus
)
from lipaidox.creator_profile.schema.profile_schema import CreatorProfileType


@strawberry.type
class LiveStreamType:
    id: strawberry.ID
    creatorId: strawberry.ID
    title: str
    description: Optional[str]
    thumbnailUrl: Optional[str]
    category: Optional[str]
    tags: List[str]
    accessType: str
    entryPrice: Optional[Decimal]
    status: str
    scheduledAt: Optional[datetime]
    startedAt: Optional[datetime]
    endedAt: Optional[datetime]
    durationSeconds: Optional[int]
    creditsUsed: int
    creditDeductionInterval: int
    streamKey: Optional[str]
    streamUrl: Optional[str]
    playbackUrl: Optional[str]
    recordingUrl: Optional[str]
    isRecorded: bool
    peakViewerCount: int
    totalViewerCount: int
    currentViewerCount: int
    totalTipsAmount: Decimal
    totalCreditsReceived: int
    totalCreditsValue: Decimal
    totalRevenue: Decimal
    chatEnabled: bool
    chatFollowersOnly: bool
    chatSubscribersOnly: bool
    createdAt: datetime
    updatedAt: datetime

    @strawberry.field
    def creator(self) -> Optional[CreatorProfileType]:
        try:
            stream = LiveStream.objects.select_related("creator").get(pk=str(self.id))
            return CreatorProfileType.from_model(stream.creator)
        except LiveStream.DoesNotExist:
            return None

    @classmethod
    def from_model(cls, instance: LiveStream):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            title=instance.title,
            description=instance.description,
            thumbnailUrl=instance.thumbnail_url,
            category=instance.category,
            tags=instance.tags_list,
            accessType=instance.access_type,
            entryPrice=instance.entry_price,
            status=instance.status,
            scheduledAt=instance.scheduled_at,
            startedAt=instance.started_at,
            endedAt=instance.ended_at,
            durationSeconds=instance.duration_seconds,
            creditsUsed=instance.credits_used,
            creditDeductionInterval=instance.credit_deduction_interval,
            streamKey=instance.stream_key,
            streamUrl=instance.stream_url,
            playbackUrl=instance.playback_url,
            recordingUrl=instance.recording_url,
            isRecorded=instance.is_recorded,
            peakViewerCount=instance.peak_viewer_count,
            totalViewerCount=instance.total_viewer_count,
            currentViewerCount=instance.current_viewer_count,
            totalTipsAmount=instance.total_tips_amount,
            totalCreditsReceived=instance.total_credits_received,
            totalCreditsValue=instance.total_credits_value,
            totalRevenue=instance.total_revenue,
            chatEnabled=instance.chat_enabled,
            chatFollowersOnly=instance.chat_followers_only,
            chatSubscribersOnly=instance.chat_subscribers_only,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class LiveStreamViewerType:
    id: strawberry.ID
    liveStreamId: strawberry.ID
    fanId: strawberry.ID
    status: str
    joinedAt: datetime
    leftAt: Optional[datetime]
    watchDurationS: Optional[int]
    ipAddress: Optional[str]
    deviceType: Optional[str]
    isSubscriber: bool
    creditsSent: int
    tipsSent: Decimal

    @classmethod
    def from_model(cls, instance: LiveStreamViewer):
        return cls(
            id=strawberry.ID(str(instance.id)),
            liveStreamId=strawberry.ID(str(instance.live_stream_id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            status=instance.status,
            joinedAt=instance.joined_at,
            leftAt=instance.left_at,
            watchDurationS=instance.watch_duration_s,
            ipAddress=str(instance.ip_address) if instance.ip_address else None,
            deviceType=instance.device_type,
            isSubscriber=instance.is_subscriber,
            creditsSent=instance.credits_sent,
            tipsSent=instance.tips_sent,
        )


@strawberry.type
class LiveStreamChatMessageType:
    id: strawberry.ID
    liveStreamId: strawberry.ID
    fanId: strawberry.ID
    message: str
    status: str
    isPinned: bool
    isCreatorMessage: bool
    deletedBy: Optional[strawberry.ID]
    deletedAt: Optional[datetime]
    sentAt: datetime

    @classmethod
    def from_model(cls, instance: LiveStreamChatMessage):
        return cls(
            id=strawberry.ID(str(instance.id)),
            liveStreamId=strawberry.ID(str(instance.live_stream_id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            message=instance.message,
            status=instance.status,
            isPinned=instance.is_pinned,
            isCreatorMessage=instance.is_creator_message,
            deletedBy=strawberry.ID(str(instance.deleted_by_id)) if instance.deleted_by else None,
            deletedAt=instance.deleted_at,
            sentAt=instance.sent_at,
        )


@strawberry.type
class LiveStreamCreditTransactionType:
    id: strawberry.ID
    liveStreamId: strawberry.ID
    giftId: strawberry.ID
    fanId: strawberry.ID
    creatorId: strawberry.ID
    creditsReceived: int
    monetaryValue: Decimal
    platformFee: Decimal
    creatorEarnings: Decimal
    animationType: str
    receivedAt: datetime

    @classmethod
    def from_model(cls, instance: LiveStreamCreditTransaction):
        return cls(
            id=strawberry.ID(str(instance.id)),
            liveStreamId=strawberry.ID(str(instance.live_stream_id)),
            giftId=strawberry.ID(str(instance.gift_id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            creditsReceived=instance.credits_received,
            monetaryValue=instance.monetary_value,
            platformFee=instance.platform_fee,
            creatorEarnings=instance.creator_earnings,
            animationType=instance.animation_type,
            receivedAt=instance.received_at,
        )


@strawberry.type
class LiveStreamMediaType:
    id: strawberry.ID
    liveStreamId: strawberry.ID
    uploadedById: strawberry.ID
    name: str
    fileUrl: str
    mimeType: str
    mediaType: str
    sizeBytes: int
    createdAt: datetime

    @classmethod
    def from_model(cls, instance):
        return cls(
            id=strawberry.ID(str(instance.id)),
            liveStreamId=strawberry.ID(str(instance.live_stream_id)),
            uploadedById=strawberry.ID(str(instance.uploaded_by_id)),
            name=instance.name,
            fileUrl=instance.file_url,
            mimeType=instance.mime_type,
            mediaType=instance.media_type,
            sizeBytes=instance.size_bytes,
            createdAt=instance.created_at,
        )


# Statistics
@strawberry.type
class LiveStreamStatisticsType:
    totalStreams: int
    liveStreams: int
    scheduledStreams: int
    endedStreams: int
    totalViewers: int
    totalRevenue: Decimal
    totalTips: Decimal
    totalCredits: int


# Input Types
@strawberry.input
class CreateLiveStreamInput:
    title: str
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = dataclasses.field(default_factory=list)
    accessType: str = LiveStreamAccessType.FREE
    entryPrice: Optional[Decimal] = None
    scheduledAt: Optional[datetime] = None
    chatEnabled: bool = True
    chatFollowersOnly: bool = False
    chatSubscribersOnly: bool = False
    isRecorded: bool = False


@strawberry.input
class UpdateLiveStreamInput:
    streamId: strawberry.ID
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    accessType: Optional[str] = None
    entryPrice: Optional[Decimal] = None
    scheduledAt: Optional[datetime] = None
    chatEnabled: Optional[bool] = None
    chatFollowersOnly: Optional[bool] = None
    chatSubscribersOnly: Optional[bool] = None


@strawberry.input
class StartStreamInput:
    streamId: strawberry.ID
    streamKey: Optional[str] = None
    streamUrl: Optional[str] = None


@strawberry.input
class SendChatMessageInput:
    streamId: strawberry.ID
    message: str


@strawberry.input
class JoinStreamInput:
    streamId: strawberry.ID
    ipAddress: Optional[str] = None
    deviceType: Optional[str] = None


@strawberry.input
class LeaveStreamInput:
    streamId: strawberry.ID
