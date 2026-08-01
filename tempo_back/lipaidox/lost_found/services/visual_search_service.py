"""
Visual Search Service - YOLOv8 + CLIP Implementation
Handles object detection, image classification, and similarity search
"""

import os
import json
import numpy as np

# Try to import AI libraries, fallback to mock implementations
try:
    import torch
    from ultralytics import YOLO
    from transformers import CLIPProcessor, CLIPModel
    import faiss
    TORCH_AVAILABLE = True
except ImportError:
    print("⚠️ PyTorch not available, using fallback implementation")
    TORCH_AVAILABLE = False

# AI Models
if TORCH_AVAILABLE:
    from ultralytics import YOLO
    from transformers import CLIPProcessor, CLIPModel

from PIL import Image
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Local imports
from ..models.lost_found import LostFoundItem, ItemImage, Match


class VisualSearchService:
    """Visual Search Service using YOLOv8 + CLIP + Faiss"""
    
    def __init__(self):
        """Initialize models and indexes"""
        print("🔍 Visual Search Service initializing...")
        
        self.torch_available = TORCH_AVAILABLE
        
        if self.torch_available:
            try:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"🔍 Visual Search Service initializing on {self.device}...")
                
                # Initialize YOLOv8 model (object detection)
                self.yolo_model = YOLO('yolov8n.pt')  # Nano model for speed
                
                # Initialize CLIP model (image embeddings)
                self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                self.clip_model.to(self.device)
                
                # Initialize Faiss index for similarity search
                self.faiss_index = self._load_or_create_faiss_index()
                
                print("✅ Full AI models loaded!")
            except Exception as e:
                print(f"❌ Failed to load AI models: {e}")
                self.torch_available = False
                self._init_fallback()
        else:
            self._init_fallback()
    
    def _init_fallback(self):
        """Initialize fallback implementation"""
        print("✅ Using fallback implementation")
        self.device = "cpu"
        self.yolo_model = None
        self.clip_model = None
        self.clip_processor = None
        self.faiss_index = None
    
    def analyze_image(self, image_file, category_hint: Optional[str] = None) -> Dict:
        """
        Complete image analysis: YOLO detection + CLIP embedding + similarity search
        """
        if self.torch_available:
            return self._analyze_with_ai(image_file, category_hint)
        else:
            return self._analyze_fallback(image_file, category_hint)
    
    def _analyze_with_ai(self, image_file, category_hint: Optional[str] = None) -> Dict:
        """Full AI analysis"""
        try:
            # 1. Object Detection with YOLOv8
            yolo_results = self._detect_objects(image_file)
            
            # 2. Extract CLIP embedding
            embedding = self._extract_clip_embedding(image_file)
            
            # 3. Find similar items
            similar_items = self._find_similar_items(embedding)
            
            # 4. Classify with category hint if provided
            classification = self._classify_image(image_file, category_hint)
            
            return {
                "status": "success",
                "method": "full_ai",
                "object_detection": yolo_results,
                "classification": classification,
                "embedding": embedding.tolist(),
                "similar_items": similar_items,
                "confidence": yolo_results.get("confidence", 0.0),
                "detected_class": yolo_results.get("class", "unknown"),
                "matches_count": len(similar_items)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "AI analysis failed"
            }
    
    def _analyze_fallback(self, image_file, category_hint: Optional[str] = None) -> Dict:
        """Fallback analysis without AI models"""
        try:
            # Basic image analysis
            img = Image.open(image_file)
            width, height = img.size
            file_size = getattr(image_file, 'size', 0)
            
            # Simple classification based on category hint or filename
            detected_class = category_hint or "unknown"
            confidence = 0.5  # Default confidence
            
            # Generate mock embedding (512-dimensional)
            embedding = np.random.rand(512).astype(np.float32)
            
            return {
                "status": "success",
                "method": "fallback",
                "object_detection": {
                    "class": detected_class,
                    "confidence": confidence,
                    "bbox": {"x": 0, "y": 0, "width": width, "height": height},
                    "all_detections": []
                },
                "classification": {
                    "top_prediction": {
                        "category": detected_class,
                        "confidence": confidence,
                        "rank": 1
                    },
                    "all_predictions": [],
                    "categories_used": [detected_class]
                },
                "embedding": embedding.tolist(),
                "similar_items": [],
                "confidence": confidence,
                "detected_class": detected_class,
                "matches_count": 0,
                "message": "Using fallback implementation - install PyTorch for full AI features"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Fallback analysis failed"
            }
    
    def _detect_objects(self, image_file) -> Dict:
        """Object detection using YOLOv8"""
        if not self.yolo_model:
            return {"class": "unknown", "confidence": 0.0, "bbox": None, "all_detections": []}
        
        try:
            # Run YOLO inference
            results = self.yolo_model(image_file, device=self.device, verbose=False)
            
            if len(results[0].boxes) > 0:
                # Get the highest confidence detection
                highest_conf_idx = torch.argmax(results[0].boxes.conf).item()
                box = results[0].boxes[highest_conf_idx]
                
                class_id = int(box.cls.item())
                class_name = results[0].names[class_id]
                confidence = float(box.conf.item())
                
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                return {
                    "class": class_name,
                    "confidence": confidence,
                    "bbox": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    },
                    "all_detections": [
                        {
                            "class": results[0].names[int(box.cls[i].item())],
                            "confidence": float(box.conf[i].item()),
                            "bbox": box.xyxy[i].tolist()
                        }
                        for i in range(len(box.cls))
                    ]
                }
            else:
                return {
                    "class": "unknown",
                    "confidence": 0.0,
                    "bbox": None,
                    "all_detections": []
                }
                
        except Exception as e:
            return {
                "class": "error",
                "confidence": 0.0,
                "bbox": None,
                "error": str(e),
                "all_detections": []
            }
    
    def _extract_clip_embedding(self, image_file) -> np.ndarray:
        """Extract CLIP embedding for similarity search"""
        try:
            # Load and preprocess image
            image = Image.open(image_file).convert('RGB')
            
            # Process with CLIP
            inputs = self.clip_processor(
                images=image, 
                return_tensors="pt"
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Extract features
            with torch.no_grad():
                embedding = self.clip_model.get_image_features(**inputs)
            
            # Normalize embedding
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            
            return embedding[0].cpu().numpy()
            
        except Exception as e:
            print(f"Error extracting CLIP embedding: {e}")
            # Return zero embedding as fallback
            return np.zeros(512)
    
    def _classify_image(self, image_file, category_hint: Optional[str] = None) -> Dict:
        """Classify image using CLIP with optional category hint"""
        try:
            # Default categories for lost & found items
            default_categories = [
                "electronics", "documents", "clothing", "jewelry", 
                "accessories", "bags", "keys", "wallets", "books",
                "sports", "tools", "medical", "other"
            ]
            
            if category_hint:
                categories = [category_hint] + [c for c in default_categories if c != category_hint]
            else:
                categories = default_categories
            
            # Load image
            image = Image.open(image_file).convert('RGB')
            
            # Create text prompts
            text_prompts = [f"a photo of a {category}" for category in categories]
            
            # Process inputs
            inputs = self.clip_processor(
                text=text_prompts,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get features
            with torch.no_grad():
                outputs = self.clip_model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=-1)
            
            # Get top predictions
            top_probs, top_indices = torch.topk(probs, min(3, len(categories)))
            
            predictions = []
            for i, (prob, idx) in enumerate(zip(top_probs[0], top_indices[0])):
                predictions.append({
                    "category": categories[idx.item()],
                    "confidence": float(prob.item()),
                    "rank": i + 1
                })
            
            return {
                "top_prediction": predictions[0] if predictions else None,
                "all_predictions": predictions,
                "categories_used": categories
            }
            
        except Exception as e:
            return {
                "top_prediction": None,
                "all_predictions": [],
                "error": str(e)
            }
    
    def _find_similar_items(self, embedding: np.ndarray, k: int = 10) -> List[Dict]:
        """Find similar items using Faiss index"""
        try:
            # Search in Faiss index
            embedding = embedding.reshape(1, -1).astype('float32')
            distances, indices = self.faiss_index.search(embedding, k)
            
            similar_items = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx >= 0:  # Valid index
                    # Find corresponding image in database
                    try:
                        image = ItemImage.objects.get(id=idx)
                        item_data = {
                            "similarity_score": float(dist),
                            "image_id": str(image.id),
                            "item_id": str(image.item.id),
                            "item_title": image.item.title,
                            "item_category": image.item.category,
                            "item_status": image.item.status,
                            "ai_class": image.ai_class,
                            "confidence": float(image.confidence_score or 0),
                            "rank": i + 1
                        }
                        similar_items.append(item_data)
                    except ItemImage.DoesNotExist:
                        continue
            
            return similar_items
            
        except Exception as e:
            print(f"Error finding similar items: {e}")
            return []
    
    def _load_or_create_faiss_index(self):
        """Load existing Faiss index or create new one"""
        try:
            index_path = os.path.join(settings.MEDIA_ROOT, 'faiss', 'visual_search.index')
            os.makedirs(os.path.dirname(index_path), exist_ok=True)
            
            if os.path.exists(index_path):
                print(f"Loading existing Faiss index from {index_path}")
                index = faiss.read_index(index_path)
                
                # Load existing embeddings from database
                self._sync_index_with_database()
                
            else:
                print("Creating new Faiss index")
                dimension = 512  # CLIP embedding size
                index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
                
                # Build index from existing images
                self._build_index_from_database(index)
                
                # Save index
                faiss.write_index(index, index_path)
            
            return index
            
        except Exception as e:
            print(f"Error loading Faiss index: {e}")
            # Create fallback index
            dimension = 512
            return faiss.IndexFlatIP(dimension)
    
    def _sync_index_with_database(self):
        """Sync Faiss index with database embeddings"""
        try:
            # Get all images with embeddings
            images = ItemImage.objects.filter(
                embedding__isnull=False,
                is_processed=True
            )
            
            embeddings = []
            for image in images:
                if image.embedding:
                    embedding = np.array(image.embedding, dtype='float32')
                    embeddings.append(embedding)
            
            if embeddings:
                embeddings_matrix = np.vstack(embeddings)
                self.faiss_index.reset()
                self.faiss_index.add(embeddings_matrix)
                print(f"Synced {len(embeddings)} embeddings to Faiss index")
            
        except Exception as e:
            print(f"Error syncing index: {e}")
    
    def _build_index_from_database(self, index):
        """Build Faiss index from existing database images"""
        try:
            images = ItemImage.objects.filter(
                embedding__isnull=False,
                is_processed=True
            )
            
            embeddings = []
            for image in images:
                if image.embedding:
                    embedding = np.array(image.embedding, dtype='float32')
                    embeddings.append(embedding)
            
            if embeddings:
                embeddings_matrix = np.vstack(embeddings)
                index.add(embeddings_matrix)
                print(f"Built index with {len(embeddings)} embeddings")
            
        except Exception as e:
            print(f"Error building index: {e}")
    
    def add_to_index(self, embedding: np.ndarray, image_id: str):
        """Add new embedding to Faiss index"""
        try:
            embedding = embedding.reshape(1, -1).astype('float32')
            self.faiss_index.add(embedding)
            
            # Save updated index
            index_path = os.path.join(settings.MEDIA_ROOT, 'faiss', 'visual_search.index')
            faiss.write_index(self.faiss_index, index_path)
            
            print(f"Added embedding for image {image_id} to index")
            
        except Exception as e:
            print(f"Error adding to index: {e}")
    
    def update_item_matches(self, item: LostFoundItem):
        """Update matches for an item based on visual similarity"""
        try:
            # Get the main image for the item
            main_image = item.images.first()
            if not main_image or not main_image.embedding:
                return
            
            embedding = np.array(main_image.embedding)
            similar_items = self._find_similar_items(embedding, k=20)
            
            # Create or update matches
            for similar in similar_items:
                similar_item_id = similar['item_id']
                
                # Skip self-matches
                if str(item.id) == similar_item_id:
                    continue
                
                try:
                    similar_item = LostFoundItem.objects.get(id=similar_item_id)
                    
                    # Create match record
                    Match.objects.update_or_create(
                        item_a=item,
                        item_b=similar_item,
                        match_type='visual',
                        defaults={
                            'similarity_score': similar['similarity_score'],
                            'visual_score': similar['similarity_score'],
                            'ai_confidence': similar.get('confidence', 0.0)
                        }
                    )
                    
                except LostFoundItem.DoesNotExist:
                    continue
            
            print(f"Updated {len(similar_items)} visual matches for item {item.id}")
            
        except Exception as e:
            print(f"Error updating item matches: {e}")
    
    def search_by_image(self, image_file, threshold: float = 0.5) -> List[Dict]:
        """Search for items by uploading an image"""
        try:
            # Analyze the uploaded image
            analysis = self.analyze_image(image_file)
            
            if analysis['status'] != 'success':
                return []
            
            # Filter similar items by threshold
            similar_items = [
                item for item in analysis['similar_items']
                if item['similarity_score'] >= threshold
            ]
            
            return similar_items
            
        except Exception as e:
            print(f"Error in image search: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """Get visual search service statistics"""
        try:
            total_images = ItemImage.objects.count()
            processed_images = ItemImage.objects.filter(is_processed=True).count()
            indexed_images = ItemImage.objects.filter(
                embedding__isnull=False,
                is_processed=True
            ).count()
            
            index_size = self.faiss_index.ntotal if self.faiss_index else 0
            
            return {
                "total_images": total_images,
                "processed_images": processed_images,
                "indexed_images": indexed_images,
                "faiss_index_size": index_size,
                "processing_rate": (processed_images / total_images * 100) if total_images > 0 else 0,
                "device": self.device,
                "models_loaded": {
                    "yolo": self.yolo_model is not None,
                    "clip": self.clip_model is not None,
                    "faiss": self.faiss_index is not None
                }
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_images": 0,
                "processed_images": 0,
                "indexed_images": 0
            }


# Singleton instance
_visual_search_service = None

def get_visual_search_service():
    """Get singleton instance of VisualSearchService"""
    global _visual_search_service
    if _visual_search_service is None:
        _visual_search_service = VisualSearchService()
    return _visual_search_service
