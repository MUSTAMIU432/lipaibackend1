import strawberry
from typing import Optional
from django.db import transaction
from django.utils import timezone
from ..models import (
    LiveStream, LiveStreamViewer, LiveStreamChatMessage, LiveStreamCreditTransaction,
    LiveStreamStatus, LiveStreamAccessType, ViewerStatus, ChatMessageStatus,
    LiveStreamMedia, MediaType,
)
from ..schema.live_streaming_schema import (
    LiveStreamType, LiveStreamViewerType, LiveStreamChatMessageType,
    LiveStreamMediaType,
    CreateLiveStreamInput, UpdateLiveStreamInput, StartStreamInput,
    SendChatMessageInput, JoinStreamInput, LeaveStreamInput
)
from lipaidox.auth.permissions import UserRoles

MAX_MEDIA_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@strawberry.type
class LiveEntryResult:
    success: bool
    code: str          # "OK" | "ALREADY_PAID" | "INSUFFICIENT_FUNDS" | "PAYMENT_FAILED" | "INVALID"
    message: str
    wallet_balance: float


def _infer_media_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return MediaType.IMAGE
    if mime_type.startswith("video/"):
        return MediaType.VIDEO
    if mime_type.startswith("audio/"):
        return MediaType.AUDIO
    if mime_type == "application/pdf":
        return MediaType.PDF
    return MediaType.PDF


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user or not user.is_authenticated:
        raise PermissionError("Authentication required. Please log in and try again.")
    return user


def require_creator(user):
    """Check if user has creator role"""
    if not hasattr(user, 'role') or user.role != UserRoles.CREATOR:
        raise PermissionError("Creator access required. Upgrade your account to go live.")
    return True


@strawberry.type
class LiveStreamingMutation:
    # Creator Mutations
    @strawberry.mutation
    def create_live_stream(self, info: strawberry.types.Info, input: CreateLiveStreamInput) -> LiveStreamType:
        """Create a new live stream"""
        user = require_auth(info)
        require_creator(user)
        
        # Validate access type and entry price
        if input.accessType == LiveStreamAccessType.PAID_ENTRY and not input.entryPrice:
            raise Exception("Entry price is required for paid entry streams")
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator profile not found")
        
        with transaction.atomic():
            stream = LiveStream(
                creator=profile,
                tenant=user.tenant,
                title=input.title,
                description=input.description,
                thumbnail_url=input.thumbnailUrl,
                category=input.category,
                access_type=input.accessType,
                entry_price=input.entryPrice,
                scheduled_at=input.scheduledAt,
                chat_enabled=input.chatEnabled,
                chat_followers_only=input.chatFollowersOnly,
                chat_subscribers_only=input.chatSubscribersOnly,
                is_recorded=input.isRecorded,
                status=LiveStreamStatus.SCHEDULED if input.scheduledAt else LiveStreamStatus.SCHEDULED
            )
            stream.tags_list = input.tags
            stream.save()
        
        return LiveStreamType.from_model(stream)
    
    @strawberry.mutation
    def update_live_stream(self, info: strawberry.types.Info, input: UpdateLiveStreamInput) -> LiveStreamType:
        """Update an existing live stream"""
        user = require_auth(info)
        require_creator(user)
        
        try:
            stream = LiveStream.objects.get(id=input.streamId)
            if stream.creator.user != user:
                raise Exception("You can only update your own streams")
            
            # Cannot update if stream is live or ended
            if stream.status in [LiveStreamStatus.LIVE, LiveStreamStatus.ENDED]:
                raise Exception("Cannot update a live or ended stream")
        except LiveStream.DoesNotExist:
            raise Exception("Stream not found")
        
        with transaction.atomic():
            if input.title is not None:
                stream.title = input.title
            if input.description is not None:
                stream.description = input.description
            if input.thumbnailUrl is not None:
                stream.thumbnail_url = input.thumbnailUrl
            if input.category is not None:
                stream.category = input.category
            if input.tags is not None:
                stream.tags_list = input.tags
            if input.accessType is not None:
                stream.access_type = input.accessType
            if input.entryPrice is not None:
                stream.entry_price = input.entryPrice
            if input.scheduledAt is not None:
                stream.scheduled_at = input.scheduledAt
            if input.chatEnabled is not None:
                stream.chat_enabled = input.chatEnabled
            if input.chatFollowersOnly is not None:
                stream.chat_followers_only = input.chatFollowersOnly
            if input.chatSubscribersOnly is not None:
                stream.chat_subscribers_only = input.chatSubscribersOnly
            
            # Validate access type and entry price
            if stream.access_type == LiveStreamAccessType.PAID_ENTRY and not stream.entry_price:
                raise Exception("Entry price is required for paid entry streams")
            
            stream.save()
        
        return LiveStreamType.from_model(stream)
    
    @strawberry.mutation
    def start_live_stream(self, info: strawberry.types.Info, input: StartStreamInput) -> LiveStreamType:
        """Start a live stream"""
        user = require_auth(info)
        require_creator(user)
        
        try:
            stream = LiveStream.objects.get(id=input.streamId)
            if stream.creator.user != user:
                raise Exception("You can only start your own streams")
            
            if stream.status != LiveStreamStatus.SCHEDULED:
                raise Exception("Only scheduled streams can be started")
        except LiveStream.DoesNotExist:
            raise Exception("Stream not found")
        
        with transaction.atomic():
            if input.streamKey:
                stream.stream_key = input.streamKey
            if input.streamUrl:
                stream.stream_url = input.streamUrl
            
            stream.start_stream()
        
        return LiveStreamType.from_model(stream)
    
    @strawberry.mutation
    def end_live_stream(self, info: strawberry.types.Info, streamId: strawberry.ID) -> LiveStreamType:
        """End a live stream"""
        user = require_auth(info)
        require_creator(user)
        
        try:
            stream = LiveStream.objects.get(id=streamId)
            if stream.creator.user != user:
                raise Exception("You can only end your own streams")
            
            if stream.status != LiveStreamStatus.LIVE:
                raise Exception("Only live streams can be ended")
        except LiveStream.DoesNotExist:
            raise Exception("Stream not found")
        
        stream.end_stream()
        return LiveStreamType.from_model(stream)
    
    @strawberry.mutation
    def cancel_live_stream(self, info: strawberry.types.Info, streamId: strawberry.ID) -> LiveStreamType:
        """Cancel a scheduled live stream"""
        user = require_auth(info)
        require_creator(user)
        
        try:
            stream = LiveStream.objects.get(id=streamId)
            if stream.creator.user != user:
                raise Exception("You can only cancel your own streams")
            
            if stream.status not in [LiveStreamStatus.SCHEDULED]:
                raise Exception("Only scheduled streams can be cancelled")
        except LiveStream.DoesNotExist:
            raise Exception("Stream not found")
        
        stream.cancel_stream()
        return LiveStreamType.from_model(stream)
    
    # Fan Mutations
    @strawberry.mutation
    def pay_live_entry(
        self,
        info: strawberry.types.Info,
        stream_id: strawberry.ID,
        payment_source: str = "WALLET",
        method: Optional[str] = None,
        simulate: Optional[str] = None,
    ) -> "LiveEntryResult":
        """Pay a paid_entry stream's fee (wallet or gateway). Idempotent — a second
        call after entry exists returns success without charging again."""
        user = require_auth(info)
        from lipaidox.wallet.services import (
            settle, credit_fan_wallet, get_or_create_fan_wallet, InsufficientFunds,
        )
        from lipaidox.wallet.models import TransactionType
        from ..models import LiveStreamEntry

        def _balance():
            return float(get_or_create_fan_wallet(user).balance)

        try:
            stream = LiveStream.objects.select_related("creator").get(id=stream_id)
        except LiveStream.DoesNotExist:
            return LiveEntryResult(success=False, code="INVALID", message="Stream not found", wallet_balance=_balance())

        if stream.access_type != LiveStreamAccessType.PAID_ENTRY:
            return LiveEntryResult(success=True, code="OK", message="No entry fee required", wallet_balance=_balance())

        if LiveStreamEntry.objects.filter(live_stream=stream, fan=user).exists():
            return LiveEntryResult(success=True, code="ALREADY_PAID", message="Entry already paid", wallet_balance=_balance())

        price = stream.entry_price or 0
        if price <= 0:
            return LiveEntryResult(success=True, code="OK", message="No entry fee", wallet_balance=_balance())

        if str(payment_source).upper() == "GATEWAY":
            from lipaidox.payment.gateways.registry import get_gateway
            from lipaidox.payment.models import ChargePurpose, ChargeStatus
            meta = {}
            if method:
                meta["method"] = method
            if simulate:
                meta["simulate"] = simulate
            charge = get_gateway().create_charge(user=user, amount=price, purpose=ChargePurpose.LIVE_ENTRY, metadata=meta)
            if charge.status != ChargeStatus.SUCCEEDED:
                return LiveEntryResult(success=False, code="PAYMENT_FAILED", message="Payment failed", wallet_balance=_balance())
            credit_fan_wallet(user, price)

        try:
            with transaction.atomic():
                entry = LiveStreamEntry.objects.create(
                    live_stream=stream, fan=user, tenant=user.tenant, amount=price,
                )
                settle(
                    fan_user=user, creator_profile=stream.creator, gross=price,
                    fee_percent=15, tx_type=TransactionType.LIVE_ENTRY,
                    description=f"Live entry: {stream.title}",
                )
        except InsufficientFunds:
            return LiveEntryResult(
                success=False, code="INSUFFICIENT_FUNDS",
                message="Insufficient wallet balance. Top up to continue.",
                wallet_balance=_balance(),
            )

        return LiveEntryResult(success=True, code="OK", message="Entry paid", wallet_balance=_balance())

    @strawberry.mutation
    def join_live_stream(self, info: strawberry.types.Info, input: JoinStreamInput) -> LiveStreamViewerType:
        """Join a live stream as a viewer"""
        user = require_auth(info)
        
        try:
            stream = LiveStream.objects.select_related("creator").get(id=input.streamId)
            if stream.status != LiveStreamStatus.LIVE:
                raise Exception("Can only join live streams")
        except LiveStream.DoesNotExist:
            raise Exception("Stream not found")

        # Access gating: owner always in; paid_entry needs a paid LiveStreamEntry;
        # subscription needs an active subscription. Callers catch the
        # "PAYMENT_REQUIRED:<price>" / "SUBSCRIPTION_REQUIRED" messages.
        is_owner = stream.creator.user_id == user.id
        if not is_owner:
            if stream.access_type == LiveStreamAccessType.PAID_ENTRY:
                from ..models import LiveStreamEntry
                if not LiveStreamEntry.objects.filter(live_stream=stream, fan=user).exists():
                    raise Exception(f"PAYMENT_REQUIRED:{stream.entry_price or 0}")
            elif stream.access_type == LiveStreamAccessType.SUBSCRIPTION:
                from lipaidox.subscriptions.services import has_active_subscription
                if not has_active_subscription(user, stream.creator):
                    raise Exception("SUBSCRIPTION_REQUIRED")

        # Check if already joined
        viewer, created = LiveStreamViewer.objects.get_or_create(
            live_stream=stream,
            fan=user,
            defaults={
                'tenant': user.tenant,
                'ip_address': input.ipAddress,
                'device_type': input.deviceType,
                'status': ViewerStatus.WATCHING
            }
        )
        
        if not created and viewer.status == ViewerStatus.LEFT:
            # Rejoin if previously left
            viewer.status = ViewerStatus.WATCHING
            viewer.left_at = None
            viewer.watch_duration_s = None
            viewer.save()
        
        # Update stream viewer count
        current_viewers = LiveStreamViewer.objects.filter(
            live_stream=stream,
            status=ViewerStatus.WATCHING
        ).count()
        stream.update_viewer_count(current_viewers)
        
        return LiveStreamViewerType.from_model(viewer)
    
    @strawberry.mutation
    def leave_live_stream(self, info: strawberry.types.Info, input: LeaveStreamInput) -> LiveStreamViewerType:
        """Leave a live stream"""
        user = require_auth(info)
        
        try:
            viewer = LiveStreamViewer.objects.get(
                live_stream_id=input.streamId,
                fan=user,
                status=ViewerStatus.WATCHING
            )
        except LiveStreamViewer.DoesNotExist:
            raise Exception("You are not currently watching this stream")
        
        viewer.leave_stream()
        
        # Update stream viewer count
        stream = viewer.live_stream
        current_viewers = LiveStreamViewer.objects.filter(
            live_stream=stream,
            status=ViewerStatus.WATCHING
        ).count()
        stream.update_viewer_count(current_viewers)
        
        return LiveStreamViewerType.from_model(viewer)
    
    @strawberry.mutation
    def send_chat_message(self, info: strawberry.types.Info, input: SendChatMessageInput) -> LiveStreamChatMessageType:
        """Send a chat message in a live stream"""
        user = require_auth(info)
        
        try:
            stream = LiveStream.objects.get(id=input.streamId)
            if stream.status != LiveStreamStatus.LIVE:
                raise Exception("Can only send messages in live streams")
            
            if not stream.chat_enabled:
                raise Exception("Chat is disabled for this stream")
        except LiveStream.DoesNotExist:
            raise Exception("Stream not found")
        
        # Validate message length
        if len(input.message) < 1 or len(input.message) > 500:
            raise Exception("Message must be between 1 and 500 characters")
        
        # Check chat restrictions
        if stream.chat_followers_only:
            # Check if fan follows creator (implementation needed)
            pass
        if stream.chat_subscribers_only:
            # Check if fan is subscribed (implementation needed)
            pass
        
        with transaction.atomic():
            message = LiveStreamChatMessage.objects.create(
                live_stream=stream,
                fan=user,
                tenant=user.tenant,
                message=input.message,
                is_creator_message=(stream.creator.user == user)
            )
        
        return LiveStreamChatMessageType.from_model(message)
    
    # Admin Mutations
    @strawberry.mutation
    def kick_viewer(self, info: strawberry.types.Info, viewerId: strawberry.ID) -> LiveStreamViewerType:
        """Kick a viewer from a live stream (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            viewer = LiveStreamViewer.objects.get(id=viewerId)
        except LiveStreamViewer.DoesNotExist:
            raise Exception("Viewer not found")
        
        viewer.status = ViewerStatus.KICKED
        viewer.leave_stream()
        
        return LiveStreamViewerType.from_model(viewer)
    
    @strawberry.mutation
    def ban_viewer(self, info: strawberry.types.Info, viewerId: strawberry.ID) -> LiveStreamViewerType:
        """Ban a viewer from live streams (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            viewer = LiveStreamViewer.objects.get(id=viewerId)
        except LiveStreamViewer.DoesNotExist:
            raise Exception("Viewer not found")
        
        viewer.status = ViewerStatus.BANNED
        viewer.leave_stream()
        
        return LiveStreamViewerType.from_model(viewer)
    
    @strawberry.mutation
    def delete_chat_message(self, info: strawberry.types.Info, messageId: strawberry.ID) -> LiveStreamChatMessageType:
        """Delete a chat message (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            message = LiveStreamChatMessage.objects.get(id=messageId)
        except LiveStreamChatMessage.DoesNotExist:
            raise Exception("Message not found")
        
        message.delete_message(user)
        return LiveStreamChatMessageType.from_model(message)
    
    @strawberry.mutation
    def pin_chat_message(self, info: strawberry.types.Info, messageId: strawberry.ID) -> LiveStreamChatMessageType:
        """Pin a chat message (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            message = LiveStreamChatMessage.objects.get(id=messageId)
        except LiveStreamChatMessage.DoesNotExist:
            raise Exception("Message not found")
        
        message.pin_message()
        return LiveStreamChatMessageType.from_model(message)
    
    @strawberry.mutation
    def unpin_chat_message(self, info: strawberry.types.Info, messageId: strawberry.ID) -> LiveStreamChatMessageType:
        """Unpin a chat message (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")

        try:
            message = LiveStreamChatMessage.objects.get(id=messageId)
        except LiveStreamChatMessage.DoesNotExist:
            raise Exception("Message not found")

        message.unpin_message()
        return LiveStreamChatMessageType.from_model(message)

    # ── Live Stream Media ─────────────────────────────────────────────────────

    @strawberry.mutation
    def add_live_stream_media(
        self,
        info: strawberry.types.Info,
        stream_id: strawberry.ID,
        name: str,
        file_url: str,
        mime_type: str,
        size_bytes: int = 0,
    ) -> LiveStreamMediaType:
        """Register an uploaded file in the stream media library (max 10 MB)."""
        user = require_auth(info)
        require_creator(user)

        if size_bytes > MAX_MEDIA_SIZE_BYTES:
            raise Exception(f"File exceeds 10 MB limit ({size_bytes / 1024 / 1024:.1f} MB).")

        try:
            stream = LiveStream.objects.get(id=stream_id)
        except LiveStream.DoesNotExist:
            raise Exception("Stream not found")

        if stream.creator.user != user:
            raise Exception("You can only add media to your own stream")

        if stream.status == LiveStreamStatus.ENDED:
            raise Exception("Cannot add media to an ended stream")

        media_type = _infer_media_type(mime_type)
        media = LiveStreamMedia.objects.create(
            live_stream=stream,
            uploaded_by=user,
            tenant=user.tenant,
            name=name,
            file_url=file_url,
            mime_type=mime_type,
            media_type=media_type,
            size_bytes=size_bytes,
        )
        return LiveStreamMediaType.from_model(media)

    @strawberry.mutation
    def remove_live_stream_media(
        self,
        info: strawberry.types.Info,
        media_id: strawberry.ID,
    ) -> bool:
        """Delete a file from the stream media library."""
        user = require_auth(info)
        try:
            media = LiveStreamMedia.objects.select_related("live_stream__creator__user").get(id=media_id)
        except LiveStreamMedia.DoesNotExist:
            return False

        if media.uploaded_by != user and media.live_stream.creator.user != user:
            raise Exception("Permission denied")

        media.delete()
        return True
