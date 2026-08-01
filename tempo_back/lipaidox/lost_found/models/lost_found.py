import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

User = get_user_model()


class LostFoundItem(models.Model):
    """Core Lost & Found item with all 6 AI features"""
    
    STATUS_CHOICES = [
        ('lost', 'Lost'),
        ('found', 'Found'),
        ('claimed', 'Claimed'),
        ('resolved', 'Resolved'),
        ('archived', 'Archived')
    ]
    
    CATEGORY_CHOICES = [
        ('electronics', 'Electronics'),
        ('documents', 'Documents'),
        ('clothing', 'Clothing'),
        ('jewelry', 'Jewelry'),
        ('accessories', 'Accessories'),
        ('bags', 'Bags & Luggage'),
        ('keys', 'Keys'),
        ('wallets', 'Wallets & Cards'),
        ('books', 'Books & Media'),
        ('sports', 'Sports Equipment'),
        ('tools', 'Tools'),
        ('medical', 'Medical Items'),
        ('pets', 'Pets'),
        ('other', 'Other')
    ]
    
    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, help_text="Brief title of the item")
    description = models.TextField(blank=True, help_text="Detailed description")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='lost')
    
    # User relationships
    reporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_items')
    claimer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='claimed_items')
    
    # Location information
    location_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    location_address = models.TextField(blank=True)
    location_description = models.TextField(blank=True, help_text="Additional location details")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reported_date = models.DateTimeField(null=True, blank=True, help_text="When item was lost/found")
    claimed_date = models.DateTimeField(null=True, blank=True)
    
    # AI Features Results (JSON fields for flexibility)
    visual_search_result = models.JSONField(default=dict, blank=True, help_text="YOLOv8 + CLIP results")
    ai_detection_result = models.JSONField(default=dict, blank=True, help_text="Nonescape AI detection")
    qr_data = models.JSONField(default=dict, blank=True, help_text="QR code data")
    price_comparison = models.JSONField(default=dict, blank=True, help_text="Scraped price data")
    deepfake_result = models.JSONField(default=dict, blank=True, help_text="DeepSafe analysis")
    community_consensus = models.JSONField(default=dict, blank=True, help_text="Voting statistics")
    
    # Additional metadata
    tags = models.JSONField(default=list, blank=True, help_text="Searchable tags")
    priority = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)], 
                                 help_text="1=Low, 5=High priority")
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'lost_found_items'
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['location_lat', 'location_lng']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_featured']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def image_count(self):
        return self.images.count()


class ItemImage(models.Model):
    """Images for Lost & Found items with embeddings"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(LostFoundItem, on_delete=models.CASCADE, related_name='images')
    
    # Image file info
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    
    # AI Analysis results
    ai_class = models.CharField(max_length=100, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    # CLIP embedding for similarity search (512-dimensional vector)
    embedding = models.JSONField(null=True, blank=True, help_text="CLIP embedding vector")
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'item_images'
        indexes = [
            models.Index(fields=['item']),
            models.Index(fields=['ai_class']),
            models.Index(fields=['is_processed']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} - {self.item.title}"


class Match(models.Model):
    """Visual and semantic matches between lost/found items"""
    
    MATCH_TYPES = [
        ('visual', 'Visual Similarity'),
        ('location', 'Location Proximity'),
        ('category', 'Category Match'),
        ('description', 'Description Similarity'),
        ('temporal', 'Time-based Match'),
        ('combined', 'Combined Score'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_a = models.ForeignKey(LostFoundItem, on_delete=models.CASCADE, related_name='matches_a')
    item_b = models.ForeignKey(LostFoundItem, on_delete=models.CASCADE, related_name='matches_b')
    
    match_type = models.CharField(max_length=20, choices=MATCH_TYPES)
    similarity_score = models.DecimalField(max_digits=5, decimal_places=4, 
                                         validators=[MinValueValidator(0), MaxValueValidator(1)])
    
    # Detailed match breakdown
    visual_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    location_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    category_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    temporal_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    # AI confidence
    ai_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    # User interaction
    is_confirmed = models.BooleanField(default=False, help_text="Confirmed by users")
    is_rejected = models.BooleanField(default=False, help_text="Rejected as false positive")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'item_matches'
        indexes = [
            models.Index(fields=['item_a']),
            models.Index(fields=['item_b']),
            models.Index(fields=['match_type']),
            models.Index(fields=['similarity_score']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['item_a', 'item_b', 'match_type']
    
    def __str__(self):
        return f"{self.item_a.title} ↔ {self.item_b.title} ({self.similarity_score})"


class Vote(models.Model):
    """Community voting on items"""
    
    VOTE_TYPES = [
        ('real', 'Real/Authentic'),
        ('fake', 'Fake/Suspicious'),
        ('helpful', 'Helpful Information'),
        ('inaccurate', 'Inaccurate Information'),
        ('spam', 'Spam'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(LostFoundItem, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    vote_type = models.CharField(max_length=20, choices=VOTE_TYPES)
    comment = models.TextField(blank=True)
    
    # Weight based on user reputation
    weight = models.DecimalField(max_digits=3, decimal_places=2, default=1.0,
                                validators=[MinValueValidator(0.1), MaxValueValidator(10.0)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'item_votes'
        indexes = [
            models.Index(fields=['item']),
            models.Index(fields=['user']),
            models.Index(fields=['vote_type']),
        ]
        unique_together = ['item', 'user']
    
    def __str__(self):
        return f"{self.user.username} - {self.vote_type} - {self.item.title}"


class Report(models.Model):
    """User reports for suspicious items"""
    
    REPORT_TYPES = [
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate Content'),
        ('false_info', 'False Information'),
        ('duplicate', 'Duplicate Item'),
        ('resolved', 'Already Resolved'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(LostFoundItem, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE)
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    reason = models.TextField()
    
    # Moderator action
    is_reviewed = models.BooleanField(default=False)
    moderator_note = models.TextField(blank=True)
    action_taken = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'item_reports'
        indexes = [
            models.Index(fields=['item']),
            models.Index(fields=['reporter']),
            models.Index(fields=['report_type']),
            models.Index(fields=['is_reviewed']),
        ]
    
    def __str__(self):
        return f"Report on {self.item.title} - {self.report_type}"


class ProductCache(models.Model):
    """Cache for scraped price comparison data"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_name = models.CharField(max_length=255, db_index=True)
    normalized_name = models.CharField(max_length=255, db_index=True)
    
    # Scraped price data
    prices = models.JSONField(default=dict, help_text="Prices from different sources")
    lowest_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    highest_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    average_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Metadata
    source_count = models.PositiveIntegerField(default=0)
    last_scraped = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_cache'
        indexes = [
            models.Index(fields=['product_name']),
            models.Index(fields=['normalized_name']),
            models.Index(fields=['last_scraped']),
            models.Index(fields=['is_active']),
        ]
        unique_together = ['product_name', 'normalized_name']
    
    def __str__(self):
        return f"{self.product_name} - ${self.average_price}"


class SearchLog(models.Model):
    """Log of search queries for analytics"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    query = models.CharField(max_length=500)
    filters = models.JSONField(default=dict, blank=True)
    results_count = models.PositiveIntegerField()

    # Performance metrics
    processing_time_ms = models.PositiveIntegerField()
    ai_features_used = models.JSONField(default=list, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'search_logs'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
            models.Index(fields=['query']),
        ]

    def __str__(self):
        return f"Search: {self.query} ({self.results_count} results)"


# ─── Community Q&A ────────────────────────────────────────────────────────────

class CommunityQuestion(models.Model):
    CATEGORY_CHOICES = [
        ('all', 'All'),
        ('business', 'Business'),
        ('hotel', 'Hotel'),
        ('jobs', 'Jobs'),
        ('tech', 'Tech'),
        ('finance', 'Finance'),
        ('health', 'Health'),
        ('travel', 'Travel'),
        ('sports', 'Sports'),
        ('education', 'Education'),
        ('general', 'General'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='community_questions')
    title = models.CharField(max_length=500)
    body = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    image_url = models.CharField(max_length=500, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    answer_count = models.PositiveIntegerField(default=0)
    # Share actions (Ask insights). Total times the question was shared.
    share_count = models.PositiveIntegerField(default=0)
    # Denormalized upvote count — incremented/decremented atomically by upvote_question.
    # Never stored as a fraction or percentage; only the raw integer lives here.
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'community_questions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['-score', '-created_at']),
            models.Index(fields=['-answer_count', '-view_count']),
        ]

    def __str__(self):
        return self.title


class QuestionView(models.Model):
    """
    One row per (authenticated user, question) pair — enforced by the unique
    constraint.  Created the first time a logged-in user opens a question;
    never updated.  Anonymous views fall back to session-based dedup in the
    query layer.
    """
    SOURCE_CHOICES = [
        ('profile', 'Profile'),
        ('feed', 'Feed'),
        ('direct', 'Direct'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(CommunityQuestion, on_delete=models.CASCADE,
                                 related_name='question_views')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='question_views')
    # Where the viewer entered the question from, captured at first view.
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='other')
    # Whether the viewer followed the question's author at view time.
    is_follower = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'community_question_views'
        unique_together = [('question', 'user')]
        indexes = [
            models.Index(fields=['question', 'user']),
            models.Index(fields=['question', 'source']),
            models.Index(fields=['question', 'viewed_at']),
        ]


class CommunityAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(CommunityQuestion, on_delete=models.CASCADE,
                                  related_name='answers')
    # Null for top-level answers; set to the parent answer for comments/replies.
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.CASCADE, related_name='replies')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='community_answers')
    body = models.TextField()
    like_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'community_answers'
        ordering = ['-like_count', '-created_at']
        indexes = [
            models.Index(fields=['question', 'parent', '-created_at']),
        ]

    def __str__(self):
        return f"Answer to: {self.question.title}"


class CommunityAnswerLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer = models.ForeignKey(CommunityAnswer, on_delete=models.CASCADE,
                                related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'community_answer_likes'
        unique_together = ['answer', 'user']


class QuestionVote(models.Model):
    """One upvote per user per question. Re-calling upvote_question removes the vote."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(CommunityQuestion, on_delete=models.CASCADE,
                                  related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='question_votes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'community_question_votes'
        constraints = [
            models.UniqueConstraint(
                fields=['question', 'user'],
                name='one_vote_per_user_per_question',
            )
        ]


# ─── Community Polls ──────────────────────────────────────────────────────────

class CommunityPoll(models.Model):
    POLL_TYPE_SINGLE   = 'single'
    POLL_TYPE_MULTIPLE = 'multiple'
    POLL_TYPE_CHOICES  = [(POLL_TYPE_SINGLE, 'Single choice'), (POLL_TYPE_MULTIPLE, 'Multiple choice')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='community_polls')
    question = models.CharField(max_length=200)
    poll_type = models.CharField(max_length=10, choices=POLL_TYPE_CHOICES, default=POLL_TYPE_SINGLE)
    max_selections = models.PositiveIntegerField(null=True, blank=True)
    duration_days = models.PositiveIntegerField(default=7)
    is_anonymous = models.BooleanField(default=False)
    verified_only = models.BooleanField(default=False)
    hide_results_until_close = models.BooleanField(default=False)
    allow_vote_change = models.BooleanField(default=True)
    allow_write_in = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True)
    total_votes = models.PositiveIntegerField(default=0)
    # Engagement analytics (Poll insights): total detail opens + share actions.
    view_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'community_polls'
        ordering = ['-total_votes', '-created_at']

    def save(self, *args, **kwargs):
        # Integrity-sensitive poll flags override allow_vote_change.
        # verified_only: tamper-evident; hide_results_until_close: no tally
        # to game, but disabling changes is also the safer choice there.
        if self.verified_only or self.hide_results_until_close:
            self.allow_vote_change = False
        super().save(*args, **kwargs)

    def __str__(self):
        return self.question


class PollOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(CommunityPoll, on_delete=models.CASCADE,
                             related_name='poll_options')
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    vote_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'community_poll_options'
        ordering = ['order']

    def __str__(self):
        return f"{self.text} (poll={self.poll_id})"


class CommunityPollVote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(CommunityPoll, on_delete=models.CASCADE,
                             related_name='votes')
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE,
                               related_name='votes', null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Vote-change tracking (enforced server-side, never trusted from client)
    change_count = models.PositiveIntegerField(default=0)
    last_changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'community_poll_votes'
        constraints = [
            models.UniqueConstraint(fields=['poll', 'user'],
                                    name='one_vote_per_user_per_poll'),
        ]

    def __str__(self):
        return f"Vote on: {self.poll.question}"


class VoteChange(models.Model):
    """
    Append-only audit log of every vote change.

    Identity (user FK) is kept internally so the audit trail is complete and
    change limits can be enforced, but it is NEVER exposed through any API
    field — not even on anonymous polls where the vote row hides identity.
    from_option / to_option use SET_NULL so option deletion doesn't orphan
    the audit row; the poll-level change history remains intact.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(CommunityPoll, on_delete=models.CASCADE,
                             related_name='vote_changes')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='poll_vote_changes')
    from_option = models.ForeignKey(PollOption, on_delete=models.SET_NULL, null=True,
                                    related_name='+')
    to_option = models.ForeignKey(PollOption, on_delete=models.SET_NULL, null=True,
                                  related_name='+')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'community_poll_vote_changes'
        ordering = ['-changed_at']
        indexes = [
            # Fast per-poll audit queries; also covers per-user-per-poll lookups.
            models.Index(fields=['poll', 'user', 'changed_at'],
                         name='vpc_poll_user_time_idx'),
        ]
