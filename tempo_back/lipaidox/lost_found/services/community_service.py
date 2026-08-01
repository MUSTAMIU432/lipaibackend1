"""
Community Service - Voting and Consensus Implementation
Handles community voting, reporting, and consensus building for lost & found items
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, F, Avg, Sum
from django.core.exceptions import ValidationError

# Local imports
from ..models.lost_found import LostFoundItem, Vote, Report

User = get_user_model()


class CommunityService:
    """Community Service for voting, reporting, and consensus"""
    
    def __init__(self):
        """Initialize community service"""
        print("👥 Community Service initializing...")
        
        # Voting weights and thresholds
        self.default_vote_weight = Decimal('1.0')
        self.min_votes_for_consensus = 3
        self.consensus_threshold = 0.6  # 60% agreement needed
        
        # Reputation system
        self.reputation_bonus_threshold = 10
        self.reputation_bonus_multiplier = Decimal('1.5')
        
        # Report thresholds
        self.auto_hide_threshold = 5  # Hide item after 5 reports
        self.auto_review_threshold = 3  # Flag for review after 3 reports
        
        print("✅ Community Service initialized!")
    
    def vote_on_item(self, item_id: str, user_id: str, vote_type: str, 
                    comment: str = "", weight: Optional[Decimal] = None) -> Dict:
        """
        Cast a vote on a lost & found item
        """
        try:
            # Validate inputs
            item = self._get_item(item_id)
            user = self._get_user(user_id)
            vote_type = self._validate_vote_type(vote_type)
            
            # Check if user has already voted
            existing_vote = Vote.objects.filter(item=item, user=user).first()
            if existing_vote:
                return self._update_existing_vote(existing_vote, vote_type, comment, weight)
            
            # Calculate vote weight based on user reputation
            calculated_weight = weight or self._calculate_vote_weight(user)
            
            # Create new vote
            vote = Vote.objects.create(
                item=item,
                user=user,
                vote_type=vote_type,
                comment=comment.strip(),
                weight=calculated_weight
            )
            
            # Update item consensus
            self._update_item_consensus(item)
            
            # Update user reputation
            self._update_user_reputation(user, 'vote')
            
            return {
                "status": "success",
                "vote_id": str(vote.id),
                "vote_type": vote_type,
                "weight": float(calculated_weight),
                "message": "Vote recorded successfully",
                "current_consensus": self._get_current_consensus(item)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to record vote"
            }
    
    def report_item(self, item_id: str, user_id: str, report_type: str, 
                   reason: str) -> Dict:
        """
        Report a lost & found item for review
        """
        try:
            # Validate inputs
            item = self._get_item(item_id)
            user = self._get_user(user_id)
            report_type = self._validate_report_type(report_type)
            
            # Check if user has already reported
            existing_report = Report.objects.filter(item=item, reporter=user).first()
            if existing_report:
                return {
                    "status": "error",
                    "error": "already_reported",
                    "message": "You have already reported this item"
                }
            
            # Create report
            report = Report.objects.create(
                item=item,
                reporter=user,
                report_type=report_type,
                reason=reason.strip()
            )
            
            # Check if item should be auto-hidden or flagged
            self._check_report_thresholds(item)
            
            return {
                "status": "success",
                "report_id": str(report.id),
                "report_type": report_type,
                "message": "Report submitted successfully",
                "total_reports": item.reports.count()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to submit report"
            }
    
    def get_item_consensus(self, item_id: str) -> Dict:
        """
        Get current consensus and voting statistics for an item
        """
        try:
            item = self._get_item(item_id)
            
            # Get vote statistics
            votes = Vote.objects.filter(item=item)
            vote_stats = self._calculate_vote_statistics(votes)
            
            # Get report statistics
            reports = Report.objects.filter(item=item)
            report_stats = self._calculate_report_statistics(reports)
            
            # Calculate overall consensus
            consensus = self._calculate_overall_consensus(vote_stats, report_stats)
            
            return {
                "status": "success",
                "item_id": str(item.id),
                "total_votes": votes.count(),
                "total_reports": reports.count(),
                "vote_statistics": vote_stats,
                "report_statistics": report_stats,
                "consensus": consensus,
                "last_updated": timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to get item consensus"
            }
    
    def get_user_voting_history(self, user_id: str, limit: int = 50) -> Dict:
        """
        Get voting history for a user
        """
        try:
            user = self._get_user(user_id)
            
            votes = Vote.objects.filter(user=user).select_related('item').order_by('-created_at')[:limit]
            
            voting_history = []
            for vote in votes:
                voting_history.append({
                    "vote_id": str(vote.id),
                    "item_id": str(vote.item.id),
                    "item_title": vote.item.title,
                    "vote_type": vote.vote_type,
                    "weight": float(vote.weight),
                    "comment": vote.comment,
                    "created_at": vote.created_at.isoformat()
                })
            
            # Calculate user statistics
            user_stats = self._calculate_user_voting_stats(user)
            
            return {
                "status": "success",
                "user_id": str(user.id),
                "voting_history": voting_history,
                "user_statistics": user_stats,
                "total_votes": votes.count()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to get voting history"
            }
    
    def get_trending_items(self, time_period_hours: int = 24, limit: int = 10) -> Dict:
        """
        Get trending items based on community engagement
        """
        try:
            cutoff_time = timezone.now() - timezone.timedelta(hours=time_period_hours)
            
            # Get items with recent activity
            recent_items = LostFoundItem.objects.filter(
                Q(votes__created_at__gte=cutoff_time) |
                Q(reports__created_at__gte=cutoff_time)
            ).distinct()
            
            trending_items = []
            for item in recent_items:
                # Calculate engagement score
                engagement_score = self._calculate_engagement_score(item, cutoff_time)
                
                trending_items.append({
                    "item_id": str(item.id),
                    "title": item.title,
                    "category": item.category,
                    "status": item.status,
                    "engagement_score": engagement_score,
                    "recent_votes": item.votes.filter(created_at__gte=cutoff_time).count(),
                    "recent_reports": item.reports.filter(created_at__gte=cutoff_time).count(),
                    "created_at": item.created_at.isoformat()
                })
            
            # Sort by engagement score
            trending_items.sort(key=lambda x: x['engagement_score'], reverse=True)
            
            return {
                "status": "success",
                "time_period_hours": time_period_hours,
                "trending_items": trending_items[:limit],
                "total_items": len(trending_items)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to get trending items"
            }
    
    def moderate_reports(self, report_id: str, moderator_id: str, 
                        action: str, note: str = "") -> Dict:
        """
        Moderate a reported item
        """
        try:
            report = Report.objects.get(id=report_id)
            moderator = self._get_user(moderator_id)
            
            # Validate action
            valid_actions = ['approve', 'hide', 'delete', 'ignore']
            if action not in valid_actions:
                raise ValueError(f"Invalid action: {action}")
            
            # Update report
            report.is_reviewed = True
            report.moderator_note = note.strip()
            report.action_taken = action
            report.reviewed_at = timezone.now()
            report.save()
            
            # Apply action to item
            item = report.item
            if action == 'hide':
                item.status = 'archived'
                item.save()
            elif action == 'delete':
                item.delete()
                return {
                    "status": "success",
                    "action": action,
                    "message": "Item deleted successfully"
                }
            
            # Update moderator reputation
            self._update_user_reputation(moderator, 'moderation')
            
            return {
                "status": "success",
                "action": action,
                "message": f"Report moderated successfully: {action}",
                "item_status": item.status if action != 'delete' else "deleted"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to moderate report"
            }
    
    def _get_item(self, item_id: str) -> LostFoundItem:
        """Get item by ID"""
        try:
            return LostFoundItem.objects.get(id=item_id)
        except LostFoundItem.DoesNotExist:
            raise ValueError("Item not found")
    
    def _get_user(self, user_id: str) -> User:
        """Get user by ID"""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValueError("User not found")
    
    def _validate_vote_type(self, vote_type: str) -> str:
        """Validate vote type"""
        valid_types = [choice[0] for choice in Vote.VOTE_TYPES]
        if vote_type not in valid_types:
            raise ValueError(f"Invalid vote type: {vote_type}")
        return vote_type
    
    def _validate_report_type(self, report_type: str) -> str:
        """Validate report type"""
        valid_types = [choice[0] for choice in Report.REPORT_TYPES]
        if report_type not in valid_types:
            raise ValueError(f"Invalid report type: {report_type}")
        return report_type
    
    def _calculate_vote_weight(self, user: User) -> Decimal:
        """Calculate vote weight based on user reputation"""
        try:
            # Get user's voting history
            vote_count = Vote.objects.filter(user=user).count()
            
            # Base weight
            weight = self.default_vote_weight
            
            # Reputation bonus
            if vote_count >= self.reputation_bonus_threshold:
                weight *= self.reputation_bonus_multiplier
            
            return weight
            
        except Exception:
            return self.default_vote_weight
    
    def _update_existing_vote(self, vote: Vote, vote_type: str, 
                            comment: str, weight: Optional[Decimal]) -> Dict:
        """Update existing vote"""
        vote.vote_type = vote_type
        vote.comment = comment.strip()
        if weight:
            vote.weight = weight
        vote.save()
        
        # Update item consensus
        self._update_item_consensus(vote.item)
        
        return {
            "status": "success",
            "vote_id": str(vote.id),
            "vote_type": vote_type,
            "weight": float(vote.weight),
            "message": "Vote updated successfully",
            "current_consensus": self._get_current_consensus(vote.item)
        }
    
    def _calculate_vote_statistics(self, votes) -> Dict:
        """Calculate voting statistics"""
        try:
            vote_counts = votes.values('vote_type').annotate(
                count=Count('id'),
                weighted_sum=Sum('weight')
            ).order_by('-weighted_sum')
            
            total_weighted_votes = votes.aggregate(total_weight=Sum('weight'))['total_weight'] or 0
            
            statistics = {}
            for vote_count in vote_counts:
                vote_type = vote_count['vote_type']
                count = vote_count['count']
                weighted_sum = vote_count['weighted_sum'] or 0
                
                percentage = (weighted_sum / total_weighted_votes * 100) if total_weighted_votes > 0 else 0
                
                statistics[vote_type] = {
                    "count": count,
                    "weighted_sum": float(weighted_sum),
                    "percentage": round(percentage, 2)
                }
            
            return statistics
            
        except Exception as e:
            print(f"Error calculating vote statistics: {e}")
            return {}
    
    def _calculate_report_statistics(self, reports) -> Dict:
        """Calculate report statistics"""
        try:
            report_counts = reports.values('report_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            total_reports = reports.count()
            reviewed_reports = reports.filter(is_reviewed=True).count()
            
            statistics = {}
            for report_count in report_counts:
                report_type = report_count['report_type']
                count = report_count['count']
                
                percentage = (count / total_reports * 100) if total_reports > 0 else 0
                
                statistics[report_type] = {
                    "count": count,
                    "percentage": round(percentage, 2)
                }
            
            return {
                "by_type": statistics,
                "total_reports": total_reports,
                "reviewed_reports": reviewed_reports,
                "pending_reviews": total_reports - reviewed_reports
            }
            
        except Exception as e:
            print(f"Error calculating report statistics: {e}")
            return {}
    
    def _calculate_overall_consensus(self, vote_stats: Dict, report_stats: Dict) -> Dict:
        """Calculate overall consensus"""
        try:
            # Get the dominant vote type
            if vote_stats:
                dominant_vote = max(vote_stats.items(), key=lambda x: x[1]['weighted_sum'])
                consensus_type = dominant_vote[0]
                consensus_strength = dominant_vote[1]['percentage']
            else:
                consensus_type = "no_votes"
                consensus_strength = 0.0
            
            # Check if consensus threshold is met
            has_consensus = consensus_strength >= (self.consensus_threshold * 100)
            
            # Consider reports in consensus
            total_reports = report_stats.get('total_reports', 0)
            report_impact = min(total_reports * 10, 50)  # Each report reduces consensus by up to 10%
            
            adjusted_consensus_strength = max(0, consensus_strength - report_impact)
            final_has_consensus = adjusted_consensus_strength >= (self.consensus_threshold * 100)
            
            return {
                "consensus_type": consensus_type,
                "consensus_strength": round(consensus_strength, 2),
                "adjusted_consensus_strength": round(adjusted_consensus_strength, 2),
                "has_consensus": has_consensus,
                "final_consensus": final_has_consensus,
                "report_impact": report_impact,
                "threshold_met": final_has_consensus
            }
            
        except Exception as e:
            print(f"Error calculating overall consensus: {e}")
            return {
                "consensus_type": "error",
                "consensus_strength": 0.0,
                "has_consensus": False
            }
    
    def _update_item_consensus(self, item: LostFoundItem):
        """Update item consensus in database"""
        try:
            consensus_data = self.get_item_consensus(str(item.id))
            item.community_consensus = consensus_data['consensus']
            item.save()
            
        except Exception as e:
            print(f"Error updating item consensus: {e}")
    
    def _get_current_consensus(self, item: LostFoundItem) -> Dict:
        """Get current consensus for an item"""
        try:
            return item.community_consensus or {}
        except Exception:
            return {}
    
    def _check_report_thresholds(self, item: LostFoundItem):
        """Check if item should be auto-hidden or flagged"""
        try:
            total_reports = item.reports.count()
            
            if total_reports >= self.auto_hide_threshold:
                # Auto-hide the item
                item.status = 'archived'
                item.save()
                
            elif total_reports >= self.auto_review_threshold:
                # Flag for review (you might want to send notification here)
                pass
                
        except Exception as e:
            print(f"Error checking report thresholds: {e}")
    
    def _calculate_engagement_score(self, item: LostFoundItem, cutoff_time) -> float:
        """Calculate engagement score for trending"""
        try:
            # Recent votes (weighted by type)
            recent_votes = item.votes.filter(created_at__gte=cutoff_time)
            vote_score = sum(vote.weight for vote in recent_votes)
            
            # Recent reports (negative impact)
            recent_reports = item.reports.filter(created_at__gte=cutoff_time).count()
            report_penalty = recent_reports * 5
            
            # View count (if available)
            view_score = item.view_count * 0.1
            
            # Time decay (newer items get higher scores)
            age_hours = (timezone.now() - item.created_at).total_seconds() / 3600
            time_bonus = max(0, 24 - age_hours) * 0.5
            
            total_score = vote_score - report_penalty + view_score + time_bonus
            return max(0, total_score)
            
        except Exception:
            return 0.0
    
    def _calculate_user_voting_stats(self, user: User) -> Dict:
        """Calculate user voting statistics"""
        try:
            votes = Vote.objects.filter(user=user)
            
            total_votes = votes.count()
            vote_types = votes.values('vote_type').annotate(count=Count('id'))
            
            # Most voted type
            most_voted = vote_types.order_by('-count').first()
            
            return {
                "total_votes": total_votes,
                "most_voted_type": most_voted['vote_type'] if most_voted else None,
                "most_voted_count": most_voted['count'] if most_voted else 0,
                "vote_types": list(vote_types.values('vote_type', 'count'))
            }
            
        except Exception:
            return {"total_votes": 0}
    
    def _update_user_reputation(self, user: User, action_type: str):
        """Update user reputation based on actions"""
        try:
            # This is a simplified reputation system
            # In practice, you'd have a separate reputation model
            
            if action_type == 'vote':
                # Increment vote count
                pass
            elif action_type == 'moderation':
                # Award reputation points for moderation
                pass
                
        except Exception as e:
            print(f"Error updating user reputation: {e}")
    
    def get_statistics(self) -> Dict:
        """Get community service statistics"""
        try:
            total_items = LostFoundItem.objects.count()
            total_votes = Vote.objects.count()
            total_reports = Report.objects.count()
            
            # Active users (users who voted in last 7 days)
            week_ago = timezone.now() - timezone.timedelta(days=7)
            active_users = Vote.objects.filter(created_at__gte=week_ago).values('user').distinct().count()
            
            # Items with consensus
            items_with_consensus = LostFoundItem.objects.filter(
                community_consensus__has_consensus=True
            ).count()
            
            return {
                "total_items": total_items,
                "total_votes": total_votes,
                "total_reports": total_reports,
                "active_users": active_users,
                "items_with_consensus": items_with_consensus,
                "consensus_rate": (items_with_consensus / total_items * 100) if total_items > 0 else 0,
                "avg_votes_per_item": (total_votes / total_items) if total_items > 0 else 0,
                "consensus_threshold": self.consensus_threshold * 100,
                "min_votes_for_consensus": self.min_votes_for_consensus
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_items": 0,
                "total_votes": 0
            }


# Singleton instance
_community_service = None

def get_community_service():
    """Get singleton instance of CommunityService"""
    global _community_service
    if _community_service is None:
        _community_service = CommunityService()
    return _community_service
