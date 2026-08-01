"""
AI Detection Service - Nonescape Implementation
Detects AI-generated images and provides detailed analysis
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

# Try to import nonescape, fallback to custom implementation if not available
try:
    from nonescape import Detector
    NONESCAPE_AVAILABLE = True
except ImportError:
    print("⚠️ Nonescape not available, using fallback AI detection")
    NONESCAPE_AVAILABLE = False

# Try to import additional ML libraries
try:
    import torch
    import torchvision.transforms as transforms
    TORCH_AVAILABLE = True
except ImportError:
    print("⚠️ PyTorch not available for advanced deepfake detection")
    TORCH_AVAILABLE = False

# Local imports
from ..models.lost_found import LostFoundItem, ItemImage


class AIDetectionService:
    """AI Detection Service using Nonescape or fallback methods"""
    
    def __init__(self):
        """Initialize AI detection models"""
        print("🤖 AI Detection Service initializing...")
        
        self.nonescape_available = NONESCAPE_AVAILABLE
        self.torch_available = TORCH_AVAILABLE
        
        if self.nonescape_available:
            try:
                self.nonescape_detector = Detector()
                self.use_nonescape = True
                print("✅ Nonescape detector loaded")
            except Exception as e:
                print(f"❌ Failed to load Nonescape: {e}")
                self.use_nonescape = False
        else:
            self.use_nonescape = False
        
        # Initialize fallback detection methods
        self._init_fallback_detectors()
        
        print("✅ AI Detection Service initialized!")
    
    def _init_fallback_detectors(self):
        """Initialize fallback detection methods"""
        # Load pre-trained models for fallback detection
        try:
            # ELA (Error Level Analysis) parameters
            self.ela_quality = 95
            self.ela_scale = 10
            
            # Noise analysis parameters
            self.noise_threshold = 0.05
            
            # Frequency analysis parameters
            self.freq_threshold = 0.1
            
            print("✅ Fallback detectors initialized")
            
        except Exception as e:
            print(f"❌ Failed to initialize fallback detectors: {e}")
    
    def analyze_image(self, image_file) -> Dict:
        """
        Complete AI detection analysis
        """
        try:
            if self.use_nonescape:
                return self._analyze_with_nonescape(image_file)
            else:
                return self._analyze_with_fallback(image_file)
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to analyze image for AI generation"
            }
    
    def _analyze_with_nonescape(self, image_file) -> Dict:
        """Analyze using Nonescape detector"""
        try:
            # Run Nonescape detection
            result = self.nonescape_detector.predict_image(image_file)
            
            # Process results
            ai_probability = result.get('ai_probability', 0.0)
            is_ai_generated = ai_probability > 0.5
            
            # Extract additional details
            generator = result.get('generator', 'unknown')
            explanation = result.get('explanation', [])
            confidence_score = result.get('confidence', ai_probability)
            
            # Run additional fallback analyses for more details
            fallback_results = self._run_fallback_analyses(image_file)
            
            return {
                "status": "success",
                "method": "nonescape",
                "is_ai_generated": is_ai_generated,
                "ai_probability": round(ai_probability * 100, 2),
                "confidence_score": round(confidence_score * 100, 2),
                "generator": generator,
                "explanation": explanation,
                "fallback_analyses": fallback_results,
                "detection_details": {
                    "primary_method": "nonescape",
                    "secondary_methods": fallback_results.keys(),
                    "overall_confidence": self._calculate_overall_confidence(ai_probability, fallback_results)
                }
            }
            
        except Exception as e:
            print(f"Nonescape analysis failed: {e}")
            # Fallback to custom methods
            return self._analyze_with_fallback(image_file)
    
    def _analyze_with_fallback(self, image_file) -> Dict:
        """Analyze using custom fallback methods"""
        try:
            fallback_results = self._run_fallback_analyses(image_file)
            
            # Calculate overall AI probability
            ai_probability = self._calculate_fallback_ai_probability(fallback_results)
            is_ai_generated = ai_probability > 0.5
            
            return {
                "status": "success",
                "method": "fallback",
                "is_ai_generated": is_ai_generated,
                "ai_probability": round(ai_probability * 100, 2),
                "confidence_score": round(ai_probability * 100, 2),
                "generator": "unknown",
                "explanation": self._generate_explanation(fallback_results),
                "fallback_analyses": fallback_results,
                "detection_details": {
                    "primary_method": "fallback",
                    "secondary_methods": fallback_results.keys(),
                    "overall_confidence": ai_probability
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Fallback analysis failed"
            }
    
    def _run_fallback_analyses(self, image_file) -> Dict:
        """Run all fallback analysis methods"""
        results = {}
        
        try:
            # 1. Error Level Analysis (ELA)
            results['ela_analysis'] = self._ela_analysis(image_file)
            
            # 2. Noise Analysis
            results['noise_analysis'] = self._noise_analysis(image_file)
            
            # 3. Frequency Analysis
            results['frequency_analysis'] = self._frequency_analysis(image_file)
            
            # 4. Texture Analysis
            results['texture_analysis'] = self._texture_analysis(image_file)
            
            # 5. Color Consistency
            results['color_consistency'] = self._color_consistency_analysis(image_file)
            
            # 6. Edge Consistency
            results['edge_consistency'] = self._edge_consistency_analysis(image_file)
            
        except Exception as e:
            print(f"Error in fallback analyses: {e}")
        
        return results
    
    def _ela_analysis(self, image_file) -> Dict:
        """Error Level Analysis - detects compression artifacts"""
        if not NUMPY_AVAILABLE:
            return {"error": "numpy not available", "ela_score": 0.0, "confidence": 0.0}
        try:
            # Load image
            img = Image.open(image_file).convert('RGB')
            
            # Save with known quality
            temp_path = os.path.join(settings.MEDIA_ROOT, 'temp_ela.jpg')
            img.save(temp_path, 'JPEG', quality=self.ela_quality)
            
            # Load compressed image
            compressed = Image.open(temp_path).convert('RGB')
            
            # Calculate difference
            ela_img = ImageChops.difference(img, compressed)
            
            # Enhance differences
            enhancer = ImageEnhance.Contrast(ela_img)
            ela_img = enhancer.enhance(self.ela_scale)
            
            # Calculate ELA score
            ela_array = np.array(ela_img)
            ela_score = np.mean(ela_array) / 255.0
            
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            # AI images tend to have uniform ELA patterns
            ela_std = np.std(ela_array) / 255.0
            
            return {
                "ela_score": round(ela_score, 4),
                "ela_std": round(ela_std, 4),
                "is_suspicious": ela_std < 0.02,  # Low standard deviation suggests AI
                "confidence": round((1 - ela_std) * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "ela_score": 0.0, "confidence": 0.0}
    
    def _noise_analysis(self, image_file) -> Dict:
        """Analyze noise patterns - AI images often have unnatural noise"""
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return {"error": "cv2/numpy not available", "noise_score": 0.0, "confidence": 0.0}
        try:
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate noise using Laplacian
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            noise_score = np.var(laplacian)
            
            # Normalize
            noise_score_normalized = min(noise_score / 1000, 1.0)
            
            # AI images often have either too little or too uniform noise
            is_suspicious = noise_score < 50 or noise_score > 500
            
            return {
                "noise_score": round(noise_score, 2),
                "noise_normalized": round(noise_score_normalized, 4),
                "is_suspicious": is_suspicious,
                "confidence": round(abs(noise_score_normalized - 0.5) * 200, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "noise_score": 0.0, "confidence": 0.0}
    
    def _frequency_analysis(self, image_file) -> Dict:
        """Frequency domain analysis - AI images have different frequency characteristics"""
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return {"error": "cv2/numpy not available", "frequency_ratio": 0.0, "confidence": 0.0}
        try:
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply FFT
            f_transform = np.fft.fft2(gray)
            f_shift = np.fft.fftshift(f_transform)
            magnitude = np.abs(f_shift)
            
            # Calculate frequency characteristics
            h, w = magnitude.shape
            center_h, center_w = h // 2, w // 2
            
            # High frequency energy
            high_freq_region = magnitude[center_h-50:center_h+50, center_w-50:center_w+50]
            high_freq_energy = np.mean(high_freq_region)
            
            # Low frequency energy
            low_freq_region = magnitude
            low_freq_energy = np.mean(low_freq_region)
            
            # Frequency ratio
            freq_ratio = high_freq_energy / low_freq_energy if low_freq_energy > 0 else 0
            
            # AI images often have unusual frequency distributions
            is_suspicious = freq_ratio < 0.1 or freq_ratio > 0.5
            
            return {
                "high_freq_energy": round(high_freq_energy, 2),
                "low_freq_energy": round(low_freq_energy, 2),
                "frequency_ratio": round(freq_ratio, 4),
                "is_suspicious": is_suspicious,
                "confidence": round(abs(freq_ratio - 0.25) * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "frequency_ratio": 0.0, "confidence": 0.0}
    
    def _texture_analysis(self, image_file) -> Dict:
        """Texture analysis - AI images often lack natural texture variation"""
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return {"error": "cv2/numpy not available", "texture_variance": 0.0, "confidence": 0.0}
        try:
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate Local Binary Pattern (simplified)
            lbp = self._calculate_lbp(gray)
            
            # Calculate texture statistics
            texture_variance = np.var(lbp)
            texture_entropy = self._calculate_entropy(lbp)
            
            # AI images often have low texture variance
            is_suspicious = texture_variance < 100
            
            return {
                "texture_variance": round(texture_variance, 2),
                "texture_entropy": round(texture_entropy, 4),
                "is_suspicious": is_suspicious,
                "confidence": round(max(0, (200 - texture_variance) / 2), 2)
            }
            
        except Exception as e:
            return {"error": str(e), "texture_variance": 0.0, "confidence": 0.0}
    
    def _color_consistency_analysis(self, image_file) -> Dict:
        """Color consistency analysis - AI images may have unnatural color distributions"""
        if not NUMPY_AVAILABLE:
            return {"error": "numpy not available", "avg_smoothness": 0.0, "confidence": 0.0}
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
            
            # AI images often have overly smooth color distributions
            is_suspicious = avg_smoothness > 0.8
            
            return {
                "color_smoothness_r": round(smoothness_r, 4),
                "color_smoothness_g": round(smoothness_g, 4),
                "color_smoothness_b": round(smoothness_b, 4),
                "avg_smoothness": round(avg_smoothness, 4),
                "is_suspicious": is_suspicious,
                "confidence": round(avg_smoothness * 100, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "avg_smoothness": 0.0, "confidence": 0.0}
    
    def _edge_consistency_analysis(self, image_file) -> Dict:
        """Edge consistency analysis - AI images may have inconsistent edge patterns"""
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return {"error": "cv2/numpy not available", "edge_density": 0.0, "confidence": 0.0}
        try:
            img = cv2.imread(str(image_file))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Canny edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Calculate edge statistics
            edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
            edge_variance = np.var(edges)
            
            # AI images often have unusual edge patterns
            is_suspicious = edge_density < 0.01 or edge_density > 0.2
            
            return {
                "edge_density": round(edge_density, 4),
                "edge_variance": round(edge_variance, 2),
                "is_suspicious": is_suspicious,
                "confidence": round(abs(edge_density - 0.05) * 200, 2)
            }
            
        except Exception as e:
            return {"error": str(e), "edge_density": 0.0, "confidence": 0.0}
    
    def _calculate_lbp(self, gray_image, radius=1, n_points=8):
        """Calculate Local Binary Pattern (simplified)"""
        h, w = gray_image.shape
        lbp = np.zeros((h, w), dtype=np.uint8)
        
        for i in range(radius, h - radius):
            for j in range(radius, w - radius):
                center = gray_image[i, j]
                binary = 0
                
                for n in range(n_points):
                    angle = 2 * np.pi * n / n_points
                    x = i + radius * np.cos(angle)
                    y = j + radius * np.sin(angle)
                    
                    # Bilinear interpolation
                    x1, y1 = int(x), int(y)
                    x2, y2 = min(x1 + 1, h - 1), min(y1 + 1, w - 1)
                    
                    dx, dy = x - x1, y - y1
                    pixel = (1 - dx) * (1 - dy) * gray_image[x1, y1] + \
                           dx * (1 - dy) * gray_image[x2, y1] + \
                           (1 - dx) * dy * gray_image[x1, y2] + \
                           dx * dy * gray_image[x2, y2]
                    
                    if pixel >= center:
                        binary |= (1 << n)
                
                lbp[i, j] = binary
        
        return lbp
    
    def _calculate_entropy(self, data):
        """Calculate entropy of data"""
        histogram = np.histogram(data, bins=256)[0]
        histogram = histogram[histogram > 0]
        probability = histogram / np.sum(histogram)
        entropy = -np.sum(probability * np.log2(probability + 1e-10))
        return entropy
    
    def _calculate_histogram_smoothness(self, histogram):
        """Calculate histogram smoothness"""
        if len(histogram) < 3:
            return 0.0
        
        # Calculate second derivative
        second_derivative = np.diff(histogram, n=2)
        smoothness = 1.0 / (1.0 + np.var(second_derivative))
        return smoothness
    
    def _calculate_overall_confidence(self, nonescape_prob, fallback_results):
        """Calculate overall confidence combining all methods"""
        try:
            confidences = [nonescape_prob]
            
            for method, result in fallback_results.items():
                if 'confidence' in result:
                    confidences.append(result['confidence'] / 100)
            
            # Weighted average (give more weight to nonescape)
            if len(confidences) > 1:
                weights = [0.6] + [0.4 / (len(confidences) - 1)] * (len(confidences) - 1)
                overall_confidence = sum(c * w for c, w in zip(confidences, weights))
            else:
                overall_confidence = confidences[0]
            
            return round(overall_confidence, 4)
            
        except Exception:
            return nonescape_prob
    
    def _calculate_fallback_ai_probability(self, fallback_results):
        """Calculate AI probability from fallback methods"""
        try:
            ai_indicators = []
            
            for method, result in fallback_results.items():
                if result.get('is_suspicious', False):
                    ai_indicators.append(1)
                else:
                    ai_indicators.append(0)
            
            if ai_indicators:
                ai_probability = sum(ai_indicators) / len(ai_indicators)
            else:
                ai_probability = 0.0
            
            return ai_probability
            
        except Exception:
            return 0.0
    
    def _generate_explanation(self, fallback_results):
        """Generate explanation based on fallback results"""
        explanations = []
        
        for method, result in fallback_results.items():
            if result.get('is_suspicious', False):
                if method == 'ela_analysis':
                    explanations.append("Unusual compression artifacts detected")
                elif method == 'noise_analysis':
                    explanations.append("Abnormal noise patterns found")
                elif method == 'frequency_analysis':
                    explanations.append("Unusual frequency characteristics")
                elif method == 'texture_analysis':
                    explanations.append("Lack of natural texture variation")
                elif method == 'color_consistency':
                    explanations.append("Overly smooth color distribution")
                elif method == 'edge_consistency':
                    explanations.append("Inconsistent edge patterns")
        
        return explanations if explanations else ["No clear AI indicators detected"]
    
    def get_statistics(self) -> Dict:
        """Get AI detection service statistics"""
        try:
            total_items = LostFoundItem.objects.count()
            analyzed_items = LostFoundItem.objects.filter(
                ai_detection_result__isnull=False
            ).count()
            
            ai_generated_count = LostFoundItem.objects.filter(
                ai_detection_result__isnull=False,
                ai_detection_result__is_ai_generated=True
            ).count()
            
            return {
                "total_items": total_items,
                "analyzed_items": analyzed_items,
                "ai_generated_count": ai_generated_count,
                "ai_generated_rate": (ai_generated_count / analyzed_items * 100) if analyzed_items > 0 else 0,
                "analysis_rate": (analyzed_items / total_items * 100) if total_items > 0 else 0,
                "nonescape_available": NONESCAPE_AVAILABLE,
                "using_nonescape": self.use_nonescape,
                "fallback_methods": ["ela", "noise", "frequency", "texture", "color", "edge"]
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_items": 0,
                "analyzed_items": 0
            }


# Singleton instance
_ai_detection_service = None

def get_ai_detection_service():
    """Get singleton instance of AIDetectionService"""
    global _ai_detection_service
    if _ai_detection_service is None:
        _ai_detection_service = AIDetectionService()
    return _ai_detection_service
