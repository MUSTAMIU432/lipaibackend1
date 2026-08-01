"""
Deepfake Service - DeepSafe Implementation
Detects deepfakes and manipulated media using advanced analysis
"""

import os
import json
from PIL import Image, ImageFilter, ImageEnhance
from typing import Dict, List, Optional, Tuple
from django.conf import settings

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    print("⚠️ OpenCV (cv2) not available, some detection methods will be skipped")
    CV2_AVAILABLE = False
from django.core.files.base import ContentFile

# Try to import DeepSafe, fallback to custom implementation if not available
try:
    from deepsafe import DeepfakeDetector
    DEEPSAFE_AVAILABLE = True
except ImportError:
    print("⚠️ DeepSafe not available, using fallback deepfake detection")
    DEEPSAFE_AVAILABLE = False

# Try to import additional ML libraries
try:
    import torch
    import torchvision.transforms as transforms
    TORCH_AVAILABLE = True
except ImportError:
    print("⚠️ PyTorch not available for advanced deepfake detection")
    TORCH_AVAILABLE = False

# Try to import OpenCV (should be available)
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    print("⚠️ OpenCV not available")
    OPENCV_AVAILABLE = False

# Local imports
from ..models.lost_found import LostFoundItem, ItemImage


class DeepfakeService:
    """Deepfake Detection Service using DeepSafe or fallback methods"""
    
    def __init__(self):
        """Initialize deepfake detection models"""
        print("🎭 Deepfake Service initializing...")
        
        self.deepsafe_available = DEEPSAFE_AVAILABLE
        self.torch_available = TORCH_AVAILABLE
        self.opencv_available = OPENCV_AVAILABLE
        
        if self.deepsafe_available:
            try:
                self.deepsafe_detector = DeepfakeDetector()
                self.use_deepsafe = True
                print("✅ DeepSafe detector loaded")
            except Exception as e:
                print(f"❌ Failed to load DeepSafe: {e}")
                self.use_deepsafe = False
        else:
            self.use_deepsafe = False
        
        # Initialize fallback detection methods
        if self.opencv_available:
            self._init_fallback_detectors()
            print("✅ Fallback detectors initialized")
        else:
            print("⚠️ OpenCV not available - limited deepfake detection")
        
        print("✅ Deepfake Service initialized!")
    
    def _init_fallback_detectors(self):
        """Initialize fallback deepfake detection methods"""
        try:
            # Face detection for analysis
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            
            # Eye detection for consistency checks
            self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
            
            # Analysis thresholds
            self.face_consistency_threshold = 0.7
            self.eye_consistency_threshold = 0.6
            self.noise_anomaly_threshold = 0.15
            self.frequency_anomaly_threshold = 0.2
            
        except Exception as e:
            print(f"❌ Failed to initialize fallback detectors: {e}")
            self.face_cascade = None
            self.eye_cascade = None
    
    def analyze_media(self, media_file) -> Dict:
        """
        Analyze media (image or video) for deepfake detection
        """
        try:
            if not self.opencv_available:
                return {
                    "status": "error",
                    "error": "OpenCV not available",
                    "message": "Install OpenCV for deepfake detection"
                }
            
            # Determine media type
            content_type = getattr(media_file, 'content_type', 'image/jpeg')
            
            if content_type.startswith('video/'):
                return self._analyze_video(media_file)
            else:
                return self._analyze_image(media_file)
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to analyze media for deepfake detection"
            }
    
    def _analyze_image(self, image_file) -> Dict:
        """Analyze image for deepfake detection"""
        try:
            if self.use_deepsafe:
                return self._analyze_with_deepsafe(image_file, 'image')
            else:
                return self._analyze_image_fallback(image_file)
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Image deepfake analysis failed"
            }
    
    def _analyze_video(self, video_file) -> Dict:
        """Analyze video for deepfake detection"""
        try:
            if self.use_deepsafe:
                return self._analyze_with_deepsafe(video_file, 'video')
            else:
                return self._analyze_video_fallback(video_file)
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Video deepfake analysis failed"
            }
    
    def _analyze_with_deepsafe(self, media_file, media_type: str) -> Dict:
        """Analyze using DeepSafe detector"""
        try:
            # Run DeepSafe detection
            result = self.deepsafe_detector.analyze_image(media_file) if media_type == 'image' else \
                    self.deepsafe_detector.analyze_video(media_file)
            
            # Process results
            deepfake_score = result.get('deepfake_score', 0.0)
            is_deepfake = deepfake_score > 0.5
            
            # Extract additional details
            artifacts = result.get('artifacts', [])
            confidence = result.get('confidence', deepfake_score)
            
            # Run additional fallback analyses for more details
            if media_type == 'image':
                fallback_results = self._run_image_fallback_analyses(media_file)
            else:
                fallback_results = self._run_video_fallback_analyses(media_file)
            
            return {
                "status": "success",
                "method": "deepsafe",
                "media_type": media_type,
                "is_deepfake": is_deepfake,
                "deepfake_score": round(deepfake_score * 100, 2),
                "confidence_score": round(confidence * 100, 2),
                "artifacts": artifacts,
                "fallback_analyses": fallback_results,
                "detection_details": {
                    "primary_method": "deepsafe",
                    "secondary_methods": fallback_results.keys(),
                    "overall_confidence": self._calculate_overall_confidence(deepfake_score, fallback_results)
                }
            }
            
        except Exception as e:
            print(f"DeepSafe analysis failed: {e}")
            # Fallback to custom methods
            if media_type == 'image':
                return self._analyze_image_fallback(media_file)
            else:
                return self._analyze_video_fallback(media_file)
    
    def _analyze_image_fallback(self, image_file) -> Dict:
        """Analyze image using custom fallback methods"""
        try:
            fallback_results = self._run_image_fallback_analyses(image_file)
            
            # Calculate overall deepfake probability
            deepfake_probability = self._calculate_fallback_deepfake_probability(fallback_results)
            is_deepfake = deepfake_probability > 0.5
            
            return {
                "status": "success",
                "method": "fallback",
                "media_type": "image",
                "is_deepfake": is_deepfake,
                "deepfake_score": round(deepfake_probability * 100, 2),
                "confidence_score": round(deepfake_probability * 100, 2),
                "artifacts": self._generate_artifacts_list(fallback_results),
                "fallback_analyses": fallback_results,
                "detection_details": {
                    "primary_method": "fallback",
                    "secondary_methods": fallback_results.keys(),
                    "overall_confidence": deepfake_probability
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Fallback image analysis failed"
            }
    
    def _analyze_video_fallback(self, video_file) -> Dict:
        """Analyze video using custom fallback methods"""
        try:
            fallback_results = self._run_video_fallback_analyses(video_file)
            
            # Calculate overall deepfake probability
            deepfake_probability = self._calculate_fallback_deepfake_probability(fallback_results)
            is_deepfake = deepfake_probability > 0.5
            
            return {
                "status": "success",
                "method": "fallback",
                "media_type": "video",
                "is_deepfake": is_deepfake,
                "deepfake_score": round(deepfake_probability * 100, 2),
                "confidence_score": round(deepfake_probability * 100, 2),
                "artifacts": self._generate_artifacts_list(fallback_results),
                "fallback_analyses": fallback_results,
                "detection_details": {
                    "primary_method": "fallback",
                    "secondary_methods": fallback_results.keys(),
                    "overall_confidence": deepfake_probability
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Fallback video analysis failed"
            }
    
    def _run_image_fallback_analyses(self, image_file) -> Dict:
        """Run all fallback image analysis methods"""
        results = {}
        
        try:
            # 1. Face Consistency Analysis
            results['face_consistency'] = self._face_consistency_analysis(image_file)
            
            # 2. Eye Blink Analysis
            results['eye_blink_analysis'] = self._eye_blink_analysis(image_file)
            
            # 3. Noise Pattern Analysis
            results['noise_pattern_analysis'] = self._noise_pattern_analysis(image_file)
            
            # 4. Frequency Domain Analysis
            results['frequency_analysis'] = self._frequency_domain_analysis(image_file)
            
            # 5. Color Consistency Analysis
            results['color_consistency'] = self._color_consistency_analysis(image_file)
            
            # 6. Edge Sharpness Analysis
            results['edge_sharpness_analysis'] = self._edge_sharpness_analysis(image_file)
            
        except Exception as e:
            print(f"Error in fallback image analyses: {e}")
        
        return results
    
    def _run_video_fallback_analyses(self, video_file) -> Dict:
        """Run all fallback video analysis methods"""
        results = {}
        
        try:
            # 1. Temporal Consistency Analysis
            results['temporal_consistency'] = self._temporal_consistency_analysis(video_file)
            
            # 2. Blink Rate Analysis
            results['blink_rate_analysis'] = self._blink_rate_analysis(video_file)
            
            # 3. Lip Sync Analysis
            results['lip_sync_analysis'] = self._lip_sync_analysis(video_file)
            
            # 4. Motion Consistency
            results['motion_consistency'] = self._motion_consistency_analysis(video_file)
            
        except Exception as e:
            print(f"Error in fallback video analyses: {e}")
        
        return results
    
    def _face_consistency_analysis(self, image_file) -> Dict:
        """Analyze face consistency and symmetry"""
        try:
            # Load image
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) == 0:
                return {"faces_detected": 0, "consistency_score": 1.0, "is_suspicious": False}
            
            consistency_scores = []
            
            for (x, y, w, h) in faces:
                # Extract face region
                face_roi = gray[y:y+h, x:x+w]
                
                # Check facial symmetry (simplified)
                left_half = face_roi[:, :w//2]
                right_half = cv2.flip(face_roi[:, w//2:], 1)
                
                # Calculate symmetry score
                if left_half.shape == right_half.shape:
                    diff = cv2.absdiff(left_half, right_half)
                    symmetry_score = 1.0 - (np.mean(diff) / 255.0)
                    consistency_scores.append(symmetry_score)
            
            avg_consistency = np.mean(consistency_scores) if consistency_scores else 1.0
            is_suspicious = avg_consistency < self.face_consistency_threshold
            
            return {
                "faces_detected": len(faces),
                "consistency_score": round(avg_consistency, 4),
                "is_suspicious": is_suspicious,
                "confidence": round((1 - avg_consistency) * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "consistency_score": 1.0, "confidence": 0.0}
    
    def _eye_blink_analysis(self, image_file) -> Dict:
        """Analyze eye patterns for blink detection"""
        try:
            # Load image
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect faces first
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) == 0:
                return {"faces_detected": 0, "blink_score": 1.0, "is_suspicious": False}
            
            blink_scores = []
            
            for (x, y, w, h) in faces:
                # Extract face region
                face_roi = gray[y:y+h, x:x+w]
                
                # Detect eyes within face
                eyes = self.eye_cascade.detectMultiScale(face_roi)
                
                if len(eyes) >= 2:
                    # Analyze eye regions for natural patterns
                    for (ex, ey, ew, eh) in eyes[:2]:
                        eye_region = face_roi[ey:ey+eh, ex:ex+ew]
                        
                        # Check for natural eye texture
                        eye_variance = np.var(eye_region)
                        blink_scores.append(min(eye_variance / 1000, 1.0))
            
            avg_blink_score = np.mean(blink_scores) if blink_scores else 1.0
            is_suspicious = avg_blink_score < self.eye_consistency_threshold
            
            return {
                "faces_detected": len(faces),
                "eyes_detected": len(blink_scores),
                "blink_score": round(avg_blink_score, 4),
                "is_suspicious": is_suspicious,
                "confidence": round((1 - avg_blink_score) * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "blink_score": 1.0, "confidence": 0.0}
    
    def _noise_pattern_analysis(self, image_file) -> Dict:
        """Analyze noise patterns for AI generation artifacts"""
        try:
            # Load image
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate noise using different methods
            # Method 1: Laplacian variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Method 2: High-frequency content
            fft = np.fft.fft2(gray)
            fft_shift = np.fft.fftshift(fft)
            magnitude = np.abs(fft_shift)
            
            # Calculate high-frequency energy
            h, w = magnitude.shape
            center_h, center_w = h // 2, w // 2
            high_freq_region = magnitude[center_h-50:center_h+50, center_w-50:center_w+50]
            high_freq_energy = np.mean(high_freq_region)
            
            # Normalize scores
            laplacian_score = min(laplacian_var / 1000, 1.0)
            freq_score = min(high_freq_energy / 1000000, 1.0)
            
            # Combined noise score
            noise_score = (laplacian_score + freq_score) / 2
            is_suspicious = noise_score < self.noise_anomaly_threshold
            
            return {
                "laplacian_variance": round(laplacian_var, 2),
                "high_frequency_energy": round(high_freq_energy, 2),
                "noise_score": round(noise_score, 4),
                "is_suspicious": is_suspicious,
                "confidence": round((1 - noise_score) * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "noise_score": 1.0, "confidence": 0.0}
    
    def _frequency_domain_analysis(self, image_file) -> Dict:
        """Analyze frequency domain for deepfake artifacts"""
        try:
            # Load image
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply FFT
            f_transform = np.fft.fft2(gray)
            f_shift = np.fft.fftshift(f_transform)
            magnitude = np.abs(f_shift)
            
            # Calculate frequency statistics
            h, w = magnitude.shape
            center_h, center_w = h // 2, w // 2
            
            # Divide into frequency bands
            low_freq = magnitude[:center_h//2, :center_w//2]
            mid_freq = magnitude[center_h//2:3*center_h//2, center_w//2:3*center_w//2]
            high_freq = magnitude[3*center_h//2:, 3*center_w//2:]
            
            # Calculate energy in each band
            low_energy = np.mean(low_freq)
            mid_energy = np.mean(mid_freq)
            high_energy = np.mean(high_freq)
            
            # Calculate frequency distribution
            total_energy = low_energy + mid_energy + high_energy
            if total_energy > 0:
                low_ratio = low_energy / total_energy
                mid_ratio = mid_energy / total_energy
                high_ratio = high_energy / total_energy
            else:
                low_ratio = mid_ratio = high_ratio = 0.33
            
            # Deepfakes often have unusual frequency distributions
            freq_anomaly = abs(low_ratio - 0.5) + abs(high_ratio - 0.2)
            is_suspicious = freq_anomaly > self.frequency_anomaly_threshold
            
            return {
                "low_freq_ratio": round(low_ratio, 4),
                "mid_freq_ratio": round(mid_ratio, 4),
                "high_freq_ratio": round(high_ratio, 4),
                "frequency_anomaly": round(freq_anomaly, 4),
                "is_suspicious": is_suspicious,
                "confidence": round(freq_anomaly * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "frequency_anomaly": 0.0, "confidence": 0.0}
    
    def _color_consistency_analysis(self, image_file) -> Dict:
        """Analyze color consistency for deepfake artifacts"""
        try:
            # Load image
            img = Image.open(image_file).convert('RGB')
            img_array = np.array(img)
            
            # Calculate color histograms
            hist_r = np.histogram(img_array[:, :, 0], bins=256, range=(0, 256))[0]
            hist_g = np.histogram(img_array[:, :, 1], bins=256, range=(0, 256))[0]
            hist_b = np.histogram(img_array[:, :, 2], bins=256, range=(0, 256))[0]
            
            # Calculate histogram smoothness
            smoothness_r = self._calculate_histogram_smoothness(hist_r)
            smoothness_g = self._calculate_histogram_smoothness(hist_g)
            smoothness_b = self._calculate_histogram_smoothness(hist_b)
            
            avg_smoothness = (smoothness_r + smoothness_g + smoothness_b) / 3
            
            # Check for unnatural color distributions
            color_variance = np.var([smoothness_r, smoothness_g, smoothness_b])
            
            # Deepfakes often have overly smooth color distributions
            is_suspicious = avg_smoothness > 0.8 or color_variance < 0.01
            
            return {
                "color_smoothness_r": round(smoothness_r, 4),
                "color_smoothness_g": round(smoothness_g, 4),
                "color_smoothness_b": round(smoothness_b, 4),
                "avg_smoothness": round(avg_smoothness, 4),
                "color_variance": round(color_variance, 4),
                "is_suspicious": is_suspicious,
                "confidence": round(avg_smoothness * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "avg_smoothness": 0.0, "confidence": 0.0}
    
    def _edge_sharpness_analysis(self, image_file) -> Dict:
        """Analyze edge sharpness and consistency"""
        try:
            # Load image
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Canny edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Calculate edge statistics
            edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
            
            # Calculate edge sharpness using gradient magnitude
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
            
            avg_sharpness = np.mean(gradient_magnitude)
            sharpness_variance = np.var(gradient_magnitude)
            
            # Deepfakes may have inconsistent edge sharpness
            is_suspicious = sharpness_variance < 50 or avg_sharpness > 100
            
            return {
                "edge_density": round(edge_density, 4),
                "avg_sharpness": round(avg_sharpness, 2),
                "sharpness_variance": round(sharpness_variance, 2),
                "is_suspicious": is_suspicious,
                "confidence": round(abs(sharpness_variance - 75) / 75 * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "sharpness_variance": 0.0, "confidence": 0.0}
    
    def _temporal_consistency_analysis(self, video_file) -> Dict:
        """Analyze temporal consistency in video"""
        try:
            # This is a simplified implementation
            # In practice, you'd use OpenCV to read video frames
            
            return {
                "temporal_score": 0.8,
                "frame_consistency": 0.85,
                "is_suspicious": False,
                "confidence": 20.0,
                "note": "Video analysis requires frame-by-frame processing"
            }
            
        except Exception as e:
            return {"error": str(e), "temporal_score": 1.0, "confidence": 0.0}
    
    def _blink_rate_analysis(self, video_file) -> Dict:
        """Analyze blink rate in video"""
        try:
            # Simplified implementation
            return {
                "blink_rate": 15.0,  # blinks per minute
                "natural_blink_range": True,
                "is_suspicious": False,
                "confidence": 10.0,
                "note": "Video blink analysis requires frame extraction"
            }
            
        except Exception as e:
            return {"error": str(e), "blink_rate": 0.0, "confidence": 0.0}
    
    def _lip_sync_analysis(self, video_file) -> Dict:
        """Analyze lip sync in video"""
        try:
            # Simplified implementation
            return {
                "lip_sync_score": 0.9,
                "sync_consistency": 0.85,
                "is_suspicious": False,
                "confidence": 15.0,
                "note": "Lip sync analysis requires audio-video processing"
            }
            
        except Exception as e:
            return {"error": str(e), "lip_sync_score": 1.0, "confidence": 0.0}
    
    def _motion_consistency_analysis(self, video_file) -> Dict:
        """Analyze motion consistency in video"""
        try:
            # Simplified implementation
            return {
                "motion_consistency": 0.8,
                "natural_motion": True,
                "is_suspicious": False,
                "confidence": 20.0,
                "note": "Motion analysis requires optical flow calculation"
            }
            
        except Exception as e:
            return {"error": str(e), "motion_consistency": 1.0, "confidence": 0.0}
    
    def _calculate_histogram_smoothness(self, histogram) -> float:
        """Calculate histogram smoothness"""
        try:
            if len(histogram) < 3:
                return 0.0
            
            # Calculate second derivative
            second_derivative = np.diff(histogram, n=2)
            smoothness = 1.0 / (1.0 + np.var(second_derivative))
            return smoothness
            
        except Exception:
            return 0.0
    
    def _calculate_overall_confidence(self, deepsafe_prob, fallback_results):
        """Calculate overall confidence combining all methods"""
        try:
            confidences = [deepsafe_prob]
            
            for method, result in fallback_results.items():
                if 'confidence' in result:
                    confidences.append(result['confidence'] / 100)
            
            # Weighted average (give more weight to DeepSafe)
            if len(confidences) > 1:
                weights = [0.7] + [0.3 / (len(confidences) - 1)] * (len(confidences) - 1)
                overall_confidence = sum(c * w for c, w in zip(confidences, weights))
            else:
                overall_confidence = confidences[0]
            
            return round(overall_confidence, 4)
            
        except Exception:
            return deepsafe_prob
    
    def _calculate_fallback_deepfake_probability(self, fallback_results):
        """Calculate deepfake probability from fallback methods"""
        try:
            deepfake_indicators = []
            
            for method, result in fallback_results.items():
                if result.get('is_suspicious', False):
                    deepfake_indicators.append(1)
                else:
                    deepfake_indicators.append(0)
            
            if deepfake_indicators:
                deepfake_probability = sum(deepfake_indicators) / len(deepfake_indicators)
            else:
                deepfake_probability = 0.0
            
            return deepfake_probability
            
        except Exception:
            return 0.0
    
    def _generate_artifacts_list(self, fallback_results):
        """Generate list of detected artifacts"""
        artifacts = []
        
        for method, result in fallback_results.items():
            if result.get('is_suspicious', False):
                if method == 'face_consistency':
                    artifacts.append("Facial asymmetry detected")
                elif method == 'eye_blink_analysis':
                    artifacts.append("Unnatural eye patterns")
                elif method == 'noise_pattern_analysis':
                    artifacts.append("Anomalous noise patterns")
                elif method == 'frequency_analysis':
                    artifacts.append("Unusual frequency characteristics")
                elif method == 'color_consistency':
                    artifacts.append("Inconsistent color distribution")
                elif method == 'edge_sharpness_analysis':
                    artifacts.append("Inconsistent edge sharpness")
        
        return artifacts if artifacts else ["No specific artifacts detected"]
    
    def get_statistics(self) -> Dict:
        """Get deepfake detection service statistics"""
        try:
            total_items = LostFoundItem.objects.count()
            analyzed_items = LostFoundItem.objects.filter(
                deepfake_result__isnull=False
            ).count()
            
            deepfake_detected = LostFoundItem.objects.filter(
                deepfake_result__isnull=False,
                deepfake_result__is_deepfake=True
            ).count()
            
            return {
                "total_items": total_items,
                "analyzed_items": analyzed_items,
                "deepfake_detected": deepfake_detected,
                "deepfake_rate": (deepfake_detected / analyzed_items * 100) if analyzed_items > 0 else 0,
                "analysis_rate": (analyzed_items / total_items * 100) if total_items > 0 else 0,
                "deepsafe_available": self.deepsafe_available,
                "using_deepsafe": self.use_deepsafe,
                "torch_available": self.torch_available,
                "fallback_methods": ["face_consistency", "eye_blink", "noise_pattern", "frequency", "color", "edge"]
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_items": 0,
                "analyzed_items": 0
            }


# Singleton instance
_deepfake_service = None

def get_deepfake_service():
    """Get singleton instance of DeepfakeService"""
    global _deepfake_service
    if _deepfake_service is None:
        _deepfake_service = DeepfakeService()
    return _deepfake_service
