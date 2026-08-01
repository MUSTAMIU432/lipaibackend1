"""
AI Service Manager - Unified Orchestrator
Coordinates all 6 AI services for Lost & Found items
"""

import os
import json
import time
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Import all AI services
from .visual_search_service import get_visual_search_service
from .ai_detection_service import get_ai_detection_service
from .qr_scanner_service import get_qr_scanner_service
from .price_compare_service import get_price_compare_service
from .deepfake_service import get_deepfake_service
from .community_service import get_community_service

# Local imports
from ..models.lost_found import LostFoundItem, ItemImage, SearchLog


class AIServiceManager:
    """Unified AI Service Manager for Lost & Found"""
    
    def __init__(self):
        """Initialize all AI services"""
        print("🤖 AI Service Manager initializing...")
        
        # Initialize all services
        self.visual_search_service = get_visual_search_service()
        self.ai_detection_service = get_ai_detection_service()
        self.qr_scanner_service = get_qr_scanner_service()
        self.price_compare_service = get_price_compare_service()
        self.deepfake_service = get_deepfake_service()
        self.community_service = get_community_service()
        
        # Service configuration
        self.service_config = {
            'visual_search': {'enabled': True, 'priority': 1},
            'ai_detection': {'enabled': True, 'priority': 2},
            'qr_scanner': {'enabled': True, 'priority': 3},
            'price_compare': {'enabled': True, 'priority': 4},
            'deepfake': {'enabled': True, 'priority': 5},
            'community': {'enabled': True, 'priority': 6}
        }
        
        # Processing options
        self.parallel_processing = True
        self.fallback_enabled = True
        self.cache_enabled = True
        
        print("✅ AI Service Manager initialized!")
    
    @classmethod
    def initialize_services(cls):
        """Initialize services (called from app config)"""
        # This method is called when Django app is ready
        pass
    
    def process_item_complete(self, image_file, item_data: Dict, 
                            category_hint: Optional[str] = None) -> Dict:
        """
        Process an item through ALL 6 AI services
        """
        try:
            start_time = time.time()
            
            # Initialize results
            results = {
                "status": "processing",
                "item_data": item_data,
                "services": {},
                "processing_time": 0,
                "errors": [],
                "summary": {}
            }
            
            # Process through each service
            if self.parallel_processing:
                # Process services in parallel (simplified version)
                results = self._process_services_parallel(image_file, item_data, category_hint, results)
            else:
                # Process services sequentially
                results = self._process_services_sequential(image_file, item_data, category_hint, results)
            
            # Calculate processing time
            results["processing_time"] = round(time.time() - start_time, 2)
            results["status"] = "completed"
            
            # Generate summary
            results["summary"] = self._generate_processing_summary(results["services"])
            
            return results
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to process item through AI services",
                "processing_time": 0
            }
    
    def process_service_specific(self, image_file, service_name: str, 
                              item_data: Dict = None) -> Dict:
        """
        Process item through a specific AI service
        """
        try:
            start_time = time.time()
            
            # Validate service name
            if service_name not in self.service_config:
                raise ValueError(f"Unknown service: {service_name}")
            
            if not self.service_config[service_name]['enabled']:
                return {
                    "status": "disabled",
                    "service": service_name,
                    "message": f"Service {service_name} is disabled"
                }
            
            # Process with specific service
            result = self._process_single_service(image_file, service_name, item_data or {})
            
            # Add processing time
            result["processing_time"] = round(time.time() - start_time, 2)
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "service": service_name,
                "error": str(e),
                "message": f"Failed to process with {service_name}"
            }
    
    def _process_services_sequential(self, image_file, item_data: Dict, 
                                   category_hint: Optional[str], results: Dict) -> Dict:
        """Process services sequentially"""
        services_ordered = sorted(
            self.service_config.items(),
            key=lambda x: x[1]['priority']
        )
        
        for service_name, config in services_ordered:
            if not config['enabled']:
                continue
            
            try:
                service_result = self._process_single_service(image_file, service_name, item_data)
                results["services"][service_name] = service_result
                
            except Exception as e:
                error_msg = f"Error in {service_name}: {str(e)}"
                results["errors"].append(error_msg)
                results["services"][service_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    def _process_services_parallel(self, image_file, item_data: Dict, 
                                category_hint: Optional[str], results: Dict) -> Dict:
        """Process services in parallel (simplified implementation)"""
        # This is a simplified version - in practice, you'd use threading or async
        return self._process_services_sequential(image_file, item_data, category_hint, results)
    
    def _process_single_service(self, image_file, service_name: str, item_data: Dict) -> Dict:
        """Process item with a single service"""
        try:
            if service_name == 'visual_search':
                return self.visual_search_service.analyze_image(image_file, item_data.get('category'))
            
            elif service_name == 'ai_detection':
                return self.ai_detection_service.analyze_image(image_file)
            
            elif service_name == 'qr_scanner':
                return self.qr_scanner_service.scan_image(image_file)
            
            elif service_name == 'price_compare':
                # Use detected class or item title for price comparison
                product_name = item_data.get('title') or item_data.get('detected_class', 'unknown')
                return self.price_compare_service.compare_prices(product_name)
            
            elif service_name == 'deepfake':
                return self.deepfake_service.analyze_media(image_file)
            
            elif service_name == 'community':
                # Community service doesn't process images directly
                return {
                    "status": "not_applicable",
                    "message": "Community service requires user interaction"
                }
            
            else:
                raise ValueError(f"Unknown service: {service_name}")
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "service": service_name
            }
    
    def _generate_processing_summary(self, services_results: Dict) -> Dict:
        """Generate summary of all service results"""
        try:
            summary = {
                "total_services": len(services_results),
                "successful_services": 0,
                "failed_services": 0,
                "key_findings": [],
                "recommendations": [],
                "confidence_scores": {}
            }
            
            for service_name, result in services_results.items():
                if result.get("status") == "success":
                    summary["successful_services"] += 1
                    
                    # Extract key findings
                    if service_name == 'visual_search':
                        if result.get("detected_class"):
                            summary["key_findings"].append(f"Detected: {result['detected_class']}")
                        if result.get("matches_count", 0) > 0:
                            summary["key_findings"].append(f"Found {result['matches_count']} similar items")
                    
                    elif service_name == 'ai_detection':
                        if result.get("is_ai_generated"):
                            summary["key_findings"].append("AI-generated image detected")
                        confidence = result.get("confidence_score", 0)
                        summary["confidence_scores"]["ai_detection"] = confidence
                    
                    elif service_name == 'qr_scanner':
                        codes_found = result.get("codes_found", 0)
                        if codes_found > 0:
                            summary["key_findings"].append(f"Found {codes_found} QR/barcode(s)")
                    
                    elif service_name == 'price_compare':
                        if result.get("prices", {}).get("summary"):
                            price_summary = result["prices"]["summary"]
                            if price_summary.get("lowest_price"):
                                summary["key_findings"].append(f"Price range: ${price_summary['lowest_price']:.2f} - ${price_summary['highest_price']:.2f}")
                    
                    elif service_name == 'deepfake':
                        if result.get("is_deepfake"):
                            summary["key_findings"].append("Potential deepfake detected")
                        confidence = result.get("confidence_score", 0)
                        summary["confidence_scores"]["deepfake"] = confidence
                
                else:
                    summary["failed_services"] += 1
            
            # Generate recommendations
            summary["recommendations"] = self._generate_recommendations(services_results)
            
            return summary
            
        except Exception as e:
            return {
                "error": str(e),
                "total_services": len(services_results),
                "successful_services": 0,
                "failed_services": len(services_results)
            }
    
    def _generate_recommendations(self, services_results: Dict) -> List[str]:
        """Generate recommendations based on service results"""
        recommendations = []
        
        try:
            # Visual search recommendations
            visual_result = services_results.get('visual_search', {})
            if visual_result.get("matches_count", 0) > 5:
                recommendations.append("High number of similar items found - consider verifying uniqueness")
            
            # AI detection recommendations
            ai_result = services_results.get('ai_detection', {})
            if ai_result.get("is_ai_generated"):
                recommendations.append("AI-generated image detected - verify authenticity")
            
            # QR scanner recommendations
            qr_result = services_results.get('qr_scanner', {})
            if qr_result.get("codes_found", 0) > 0:
                recommendations.append("QR/barcode found - extract and verify contact information")
            
            # Deepfake recommendations
            deepfake_result = services_results.get('deepfake', {})
            if deepfake_result.get("is_deepfake"):
                recommendations.append("Potential deepfake detected - manual review recommended")
            
            # Price comparison recommendations
            price_result = services_results.get('price_compare', {})
            if price_result.get("prices", {}).get("summary"):
                price_summary = price_result["prices"]["summary"]
                if price_summary.get("price_range", 0) > 100:
                    recommendations.append("High price variation - verify item details and condition")
            
            # General recommendations
            failed_services = [name for name, result in services_results.items() 
                             if result.get("status") != "success"]
            if failed_services:
                recommendations.append(f"Some services failed: {', '.join(failed_services)}")
            
            return recommendations
            
        except Exception:
            return []
    
    def create_lost_found_item(self, image_file, item_data: Dict, 
                              user_id: Optional[str] = None) -> Dict:
        """
        Create a new Lost & Found item with full AI processing
        """
        try:
            start_time = time.time()
            
            # Step 1: Process image through all AI services
            ai_results = self.process_item_complete(image_file, item_data, item_data.get('category'))
            
            # Step 2: Create LostFoundItem
            item = self._create_item_record(item_data, user_id, ai_results)
            
            # Step 3: Save image and create ItemImage record
            image_record = self._save_image_record(image_file, item, ai_results)
            
            # Step 4: Update visual search index
            if ai_results["services"].get("visual_search", {}).get("status") == "success":
                visual_result = ai_results["services"]["visual_search"]
                if visual_result.get("embedding"):
                    self.visual_search_service.add_to_index(
                        visual_result["embedding"], 
                        str(image_record.id)
                    )
                    self.visual_search_service.update_item_matches(item)
            
            # Step 5: Log search
            self._log_search(item_data.get("title", ""), ai_results)
            
            total_time = time.time() - start_time
            
            return {
                "status": "success",
                "item_id": str(item.id),
                "image_id": str(image_record.id),
                "ai_results": ai_results,
                "processing_time": round(total_time, 2),
                "message": "Lost & Found item created successfully with AI analysis"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to create Lost & Found item"
            }
    
    def _create_item_record(self, item_data: Dict, user_id: Optional[str], ai_results: Dict) -> LostFoundItem:
        """Create LostFoundItem record with AI results"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Extract user
            user = User.objects.get(id=user_id) if user_id else None
            
            # Extract AI results
            services = ai_results.get("services", {})
            
            # Create item
            item = LostFoundItem.objects.create(
                title=item_data.get("title", ""),
                description=item_data.get("description", ""),
                category=item_data.get("category", ""),
                status=item_data.get("status", "lost"),
                reporter=user,
                
                # AI Results
                visual_search_result=services.get("visual_search", {}),
                ai_detection_result=services.get("ai_detection", {}),
                qr_data=services.get("qr_scanner", {}),
                price_comparison=services.get("price_compare", {}),
                deepfake_result=services.get("deepfake", {}),
                community_consensus=services.get("community", {}),
                
                # Location data
                location_lat=item_data.get("location_lat"),
                location_lng=item_data.get("location_lng"),
                location_address=item_data.get("location_address", ""),
                location_description=item_data.get("location_description", ""),
                
                # Additional metadata
                tags=item_data.get("tags", []),
                priority=item_data.get("priority", 1),
                is_featured=item_data.get("is_featured", False)
            )
            
            return item
            
        except Exception as e:
            raise Exception(f"Failed to create item record: {e}")
    
    def _save_image_record(self, image_file, item: LostFoundItem, ai_results: Dict) -> ItemImage:
        """Save image and create ItemImage record"""
        try:
            # Save image file
            file_path = default_storage.save(f"lost_found/{item.id}/{image_file.name}", image_file)
            
            # Get image dimensions
            from PIL import Image as PILImage
            img = PILImage.open(image_file)
            width, height = img.size
            
            # Extract AI classification
            visual_result = ai_results.get("services", {}).get("visual_search", {})
            ai_class = visual_result.get("detected_class", "unknown")
            confidence = visual_result.get("confidence", 0.0)
            embedding = visual_result.get("embedding")
            
            # Create image record
            image_record = ItemImage.objects.create(
                item=item,
                original_filename=image_file.name,
                file_path=file_path,
                file_size=image_file.size,
                content_type=getattr(image_file, 'content_type', 'image/jpeg'),
                width=width,
                height=height,
                ai_class=ai_class,
                confidence_score=confidence,
                embedding=embedding,
                is_processed=True
            )
            
            return image_record
            
        except Exception as e:
            raise Exception(f"Failed to save image record: {e}")
    
    def _log_search(self, query: str, ai_results: Dict):
        """Log search for analytics"""
        try:
            SearchLog.objects.create(
                query=query,
                filters={},
                results_count=ai_results.get("summary", {}).get("successful_services", 0),
                processing_time_ms=int(ai_results.get("processing_time", 0) * 1000),
                ai_features_used=list(ai_results.get("services", {}).keys())
            )
        except Exception as e:
            print(f"Failed to log search: {e}")
    
    def search_similar_items(self, image_file, threshold: float = 0.5) -> Dict:
        """Search for similar items using visual search"""
        try:
            return self.visual_search_service.search_by_image(image_file, threshold)
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to search similar items"
            }
    
    def get_service_health(self) -> Dict:
        """Get health status of all AI services"""
        try:
            health_status = {}
            
            # Check each service
            services = [
                ("visual_search", self.visual_search_service),
                ("ai_detection", self.ai_detection_service),
                ("qr_scanner", self.qr_scanner_service),
                ("price_compare", self.price_compare_service),
                ("deepfake", self.deepfake_service),
                ("community", self.community_service)
            ]
            
            for service_name, service_instance in services:
                try:
                    stats = service_instance.get_statistics()
                    health_status[service_name] = {
                        "status": "healthy",
                        "statistics": stats
                    }
                except Exception as e:
                    health_status[service_name] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
            
            return {
                "status": "completed",
                "services": health_status,
                "overall_health": self._calculate_overall_health(health_status)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _calculate_overall_health(self, health_status: Dict) -> Dict:
        """Calculate overall system health"""
        try:
            total_services = len(health_status)
            healthy_services = sum(1 for service in health_status.values() if service["status"] == "healthy")
            
            health_percentage = (healthy_services / total_services * 100) if total_services > 0 else 0
            
            if health_percentage >= 80:
                overall_status = "excellent"
            elif health_percentage >= 60:
                overall_status = "good"
            elif health_percentage >= 40:
                overall_status = "fair"
            else:
                overall_status = "poor"
            
            return {
                "status": overall_status,
                "healthy_services": healthy_services,
                "total_services": total_services,
                "health_percentage": round(health_percentage, 2)
            }
            
        except Exception:
            return {
                "status": "unknown",
                "healthy_services": 0,
                "total_services": len(health_status),
                "health_percentage": 0
            }
    
    def get_statistics(self) -> Dict:
        """Get comprehensive statistics for all services"""
        try:
            stats = {
                "service_manager": {
                    "total_services": len(self.service_config),
                    "enabled_services": sum(1 for config in self.service_config.values() if config['enabled']),
                    "parallel_processing": self.parallel_processing,
                    "fallback_enabled": self.fallback_enabled,
                    "cache_enabled": self.cache_enabled
                },
                "services": {}
            }
            
            # Get statistics from each service
            services = [
                ("visual_search", self.visual_search_service),
                ("ai_detection", self.ai_detection_service),
                ("qr_scanner", self.qr_scanner_service),
                ("price_compare", self.price_compare_service),
                ("deepfake", self.deepfake_service),
                ("community", self.community_service)
            ]
            
            for service_name, service_instance in services:
                try:
                    stats["services"][service_name] = service_instance.get_statistics()
                except Exception as e:
                    stats["services"][service_name] = {"error": str(e)}
            
            return stats
            
        except Exception as e:
            return {
                "error": str(e),
                "service_manager": {},
                "services": {}
            }


# Singleton instance
_ai_service_manager = None

def get_ai_service_manager():
    """Get singleton instance of AIServiceManager"""
    global _ai_service_manager
    if _ai_service_manager is None:
        _ai_service_manager = AIServiceManager()
    return _ai_service_manager
