"""
QR Scanner Service - pyzbar Implementation
Scans and decodes QR codes and barcodes from images
"""

import os
import json
import re
from PIL import Image, ImageEnhance, ImageFilter
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from django.conf import settings

# Try to import pyzbar, fallback to OpenCV if not available
try:
    from pyzbar import pyzbar
    from pyzbar.pyzbar import ZBarSymbol
    PYZBAR_AVAILABLE = True
except ImportError:
    print("⚠️ pyzbar not available, using OpenCV fallback")
    PYZBAR_AVAILABLE = False

# Try to import OpenCV (should be available)
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    print("⚠️ OpenCV not available, QR scanning will be limited")
    OPENCV_AVAILABLE = False

# Local imports
from ..models.lost_found import LostFoundItem, ItemImage


class QRScannerService:
    """QR Scanner Service using pyzbar or OpenCV fallback"""
    
    def __init__(self):
        """Initialize QR scanner"""
        print("📷 QR Scanner Service initializing...")
        
        self.pyzbar_available = PYZBAR_AVAILABLE
        self.opencv_available = OPENCV_AVAILABLE
        
        # Initialize OpenCV QR detector as fallback
        if self.opencv_available:
            self.qr_detector = cv2.QRCodeDetector()
            print("✅ OpenCV QR detector available as fallback")
        else:
            self.qr_detector = None
            print("⚠️ No QR detection libraries available")
        
        if self.pyzbar_available:
            print("✅ pyzbar scanner initialized")
        
        # Supported barcode types
        self.supported_types = [
            'QRCODE', 'CODE128', 'CODE39', 'EAN13', 'EAN8', 
            'UPC-A', 'UPC-E', 'ISBN10', 'ISBN13', 'DATA MATRIX'
        ]
        
        print("✅ QR Scanner Service initialized!")
    
    def scan_image(self, image_file, enhance_image: bool = True) -> Dict:
        """
        Scan image for QR codes and barcodes
        """
        try:
            if not self.opencv_available:
                return {
                    "status": "error",
                    "error": "OpenCV not available",
                    "message": "Install OpenCV to enable QR scanning"
                }
            
            # Load and optionally enhance image
            image = self._load_and_prepare_image(image_file, enhance_image)
            
            if self.pyzbar_available:
                return self._scan_with_pyzbar(image)
            else:
                return self._scan_with_opencv(image)
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to scan image for QR codes"
            }
    
    def _load_and_prepare_image(self, image_file, enhance: bool = True) -> Image.Image:
        """Load and prepare image for scanning"""
        try:
            # Load image
            image = Image.open(image_file).convert('RGB')
            
            if enhance:
                # Enhance image for better QR detection
                image = self._enhance_image_for_qr(image)
            
            return image
            
        except Exception as e:
            raise Exception(f"Failed to load image: {e}")
    
    def _enhance_image_for_qr(self, image: Image.Image) -> Image.Image:
        """Enhance image for better QR code detection"""
        try:
            # Convert to grayscale for processing
            gray = image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(gray)
            enhanced = enhancer.enhance(2.0)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = enhancer.enhance(2.0)
            
            # Apply slight blur to reduce noise
            enhanced = enhanced.filter(ImageFilter.MedianFilter(size=3))
            
            return enhanced
            
        except Exception as e:
            print(f"Image enhancement failed: {e}")
            return image
    
    def _scan_with_pyzbar(self, image: Image.Image) -> Dict:
        """Scan using pyzbar library"""
        try:
            # Convert to numpy array for pyzbar
            image_array = np.array(image)
            
            # Scan for codes
            decoded_objects = pyzbar.decode(image_array, symbols=[ZBarSymbol.QRCODE])
            
            if not decoded_objects:
                # Try other barcode types if no QR codes found
                decoded_objects = pyzbar.decode(image_array)
            
            results = []
            for obj in decoded_objects:
                result = self._process_pyzbar_result(obj)
                results.append(result)
            
            return {
                "status": "success",
                "method": "pyzbar",
                "codes_found": len(results),
                "codes": results,
                "total_codes": len(results)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "pyzbar scanning failed"
            }
    
    def _scan_with_opencv(self, image: Image.Image) -> Dict:
        """Scan using OpenCV QR detector (fallback)"""
        try:
            # Convert to numpy array
            image_array = np.array(image)
            
            # Detect QR codes
            decoded_text, points, _ = self.qr_detector.detectAndDecode(image_array)
            
            results = []
            
            if decoded_text:
                result = self._process_opencv_result(decoded_text, points)
                results.append(result)
            
            # Try to detect other barcodes using template matching (basic)
            barcode_results = self._detect_barcodes_opencv(image_array)
            results.extend(barcode_results)
            
            return {
                "status": "success",
                "method": "opencv",
                "codes_found": len(results),
                "codes": results,
                "total_codes": len(results)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "OpenCV scanning failed"
            }
    
    def _process_pyzbar_result(self, decoded_object) -> Dict:
        """Process pyzbar decoded object"""
        try:
            # Extract data
            data = decoded_object.data.decode('utf-8')
            code_type = decoded_object.type
            
            # Get bounding box
            rect = decoded_object.rect
            bbox = {
                "x": rect.left,
                "y": rect.top,
                "width": rect.width,
                "height": rect.height
            }
            
            # Get polygon points
            polygon = [(point.x, point.y) for point in decoded_object.polygon]
            
            # Quality assessment
            quality = decoded_object.quality if hasattr(decoded_object, 'quality') else None
            
            # Parse content
            parsed_content = self._parse_qr_content(data)
            
            return {
                "content": data,
                "type": code_type,
                "bbox": bbox,
                "polygon": polygon,
                "quality": quality,
                "parsed_content": parsed_content,
                "is_valid": len(data.strip()) > 0,
                "data_type": self._detect_data_type(data)
            }
            
        except Exception as e:
            return {
                "content": "",
                "type": "unknown",
                "error": str(e),
                "is_valid": False
            }
    
    def _process_opencv_result(self, decoded_text: str, points) -> Dict:
        """Process OpenCV QR detection result"""
        try:
            # Convert points to list of tuples
            if points is not None:
                polygon = [(int(point[0][0]), int(point[0][1])) for point in points]
                
                # Calculate bounding box
                x_coords = [p[0] for p in polygon]
                y_coords = [p[1] for p in polygon]
                bbox = {
                    "x": min(x_coords),
                    "y": min(y_coords),
                    "width": max(x_coords) - min(x_coords),
                    "height": max(y_coords) - min(y_coords)
                }
            else:
                polygon = []
                bbox = {"x": 0, "y": 0, "width": 0, "height": 0}
            
            # Parse content
            parsed_content = self._parse_qr_content(decoded_text)
            
            return {
                "content": decoded_text,
                "type": "QRCODE",
                "bbox": bbox,
                "polygon": polygon,
                "quality": None,
                "parsed_content": parsed_content,
                "is_valid": len(decoded_text.strip()) > 0,
                "data_type": self._detect_data_type(decoded_text)
            }
            
        except Exception as e:
            return {
                "content": decoded_text or "",
                "type": "QRCODE",
                "error": str(e),
                "is_valid": False
            }
    
    def _detect_barcodes_opencv(self, image_array) -> List[Dict]:
        """Basic barcode detection using OpenCV (fallback)"""
        try:
            results = []
            
            # Convert to grayscale
            gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
            
            # Apply threshold
            _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Find contours
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                # Filter for barcode-like shapes
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                
                # Barcodes are typically wider than they are tall
                if 2 < aspect_ratio < 10 and w > 50 and h > 10:
                    # Extract barcode region
                    barcode_region = gray[y:y+h, x:x+w]
                    
                    # Try to decode (this is a simplified approach)
                    # In practice, you'd need a proper barcode decoder
                    result = {
                        "content": "BARCODE_DETECTED",  # Placeholder
                        "type": "UNKNOWN_BARCODE",
                        "bbox": {"x": x, "y": y, "width": w, "height": h},
                        "polygon": [(x, y), (x+w, y), (x+w, y+h), (x, y+h)],
                        "quality": None,
                        "parsed_content": {"type": "barcode", "confidence": 0.5},
                        "is_valid": True,
                        "data_type": "barcode"
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Barcode detection failed: {e}")
            return []
    
    def _parse_qr_content(self, content: str) -> Dict:
        """Parse and categorize QR code content"""
        try:
            content = content.strip()
            
            if not content:
                return {"type": "empty", "data": {}}
            
            # URL detection
            if content.startswith(('http://', 'https://', 'www.')):
                return self._parse_url_content(content)
            
            # Email detection
            if content.startswith(('mailto:', 'email:')) or '@' in content:
                return self._parse_email_content(content)
            
            # Phone detection
            if content.startswith(('tel:', 'phone:', 'call:')) or self._is_phone_number(content):
                return self._parse_phone_content(content)
            
            # WiFi detection
            if content.startswith(('WIFI:', 'WiFi:')):
                return self._parse_wifi_content(content)
            
            # vCard detection
            if content.startswith('BEGIN:VCARD'):
                return self._parse_vcard_content(content)
            
            # Geographic coordinates
            if content.startswith(('geo:', 'location:')) or self._is_coordinates(content):
                return self._parse_geo_content(content)
            
            # SMS detection
            if content.startswith(('sms:', 'smsto:', 'mmsto:')):
                return self._parse_sms_content(content)
            
            # Plain text with structure
            if self._is_structured_text(content):
                return self._parse_structured_text(content)
            
            # Generic text
            return {
                "type": "text",
                "data": {
                    "content": content,
                    "length": len(content),
                    "encoding": "utf-8"
                }
            }
            
        except Exception as e:
            return {
                "type": "error",
                "data": {"error": str(e), "content": content}
            }
    
    def _parse_url_content(self, content: str) -> Dict:
        """Parse URL content"""
        try:
            # Clean URL
            if content.startswith('www.'):
                content = 'https://' + content
            
            parsed = urlparse(content)
            
            return {
                "type": "url",
                "data": {
                    "url": content,
                    "domain": parsed.netloc,
                    "path": parsed.path,
                    "query": parse_qs(parsed.query),
                    "scheme": parsed.scheme
                }
            }
            
        except Exception:
            return {
                "type": "url",
                "data": {"url": content, "domain": "unknown"}
            }
    
    def _parse_email_content(self, content: str) -> Dict:
        """Parse email content"""
        try:
            if content.startswith('mailto:'):
                email = content[7:].split('?')[0]
                query_part = content.split('?')[1] if '?' in content else ''
                params = parse_qs(query_part)
            else:
                email = content
                params = {}
            
            return {
                "type": "email",
                "data": {
                    "email": email,
                    "subject": params.get('subject', [''])[0],
                    "body": params.get('body', [''])[0]
                }
            }
            
        except Exception:
            return {
                "type": "email",
                "data": {"email": content}
            }
    
    def _parse_phone_content(self, content: str) -> Dict:
        """Parse phone content"""
        try:
            if content.startswith(('tel:', 'phone:', 'call:')):
                phone = content.split(':', 1)[1]
            else:
                phone = content
            
            # Clean phone number
            phone = re.sub(r'[^\d+]', '', phone)
            
            return {
                "type": "phone",
                "data": {
                    "phone": phone,
                    "formatted": self._format_phone_number(phone)
                }
            }
            
        except Exception:
            return {
                "type": "phone",
                "data": {"phone": content}
            }
    
    def _parse_wifi_content(self, content: str) -> Dict:
        """Parse WiFi content"""
        try:
            # Format: WIFI:T:WPA;S:NetworkName;P:Password;;
            wifi_data = {}
            
            parts = content.split(';')
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    if key == 'T':
                        wifi_data['type'] = value
                    elif key == 'S':
                        wifi_data['ssid'] = value
                    elif key == 'P':
                        wifi_data['password'] = value
                    elif key == 'H':
                        wifi_data['hidden'] = value == 'true'
            
            return {
                "type": "wifi",
                "data": wifi_data
            }
            
        except Exception:
            return {
                "type": "wifi",
                "data": {"content": content}
            }
    
    def _parse_vcard_content(self, content: str) -> Dict:
        """Parse vCard content"""
        try:
            vcard_data = {}
            lines = content.split('\n')
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    if key.startswith('FN'):
                        vcard_data['full_name'] = value
                    elif key.startswith('TEL'):
                        vcard_data['phone'] = value
                    elif key.startswith('EMAIL'):
                        vcard_data['email'] = value
                    elif key.startswith('ORG'):
                        vcard_data['organization'] = value
            
            return {
                "type": "vcard",
                "data": vcard_data
            }
            
        except Exception:
            return {
                "type": "vcard",
                "data": {"content": content}
            }
    
    def _parse_geo_content(self, content: str) -> Dict:
        """Parse geographic content"""
        try:
            if content.startswith('geo:'):
                coords = content[4:].split('?')[0]
            else:
                coords = content
            
            if ',' in coords:
                lat, lng = coords.split(',', 1)
                return {
                    "type": "location",
                    "data": {
                        "latitude": float(lat),
                        "longitude": float(lng),
                        "coordinates": f"{lat},{lng}"
                    }
                }
            
            return {
                "type": "location",
                "data": {"coordinates": coords}
            }
            
        except Exception:
            return {
                "type": "location",
                "data": {"coordinates": content}
            }
    
    def _parse_sms_content(self, content: str) -> Dict:
        """Parse SMS content"""
        try:
            if content.startswith(('sms:', 'smsto:', 'mmsto:')):
                parts = content.split(':', 1)[1]
                phone, body = parts.split('?', 1) if '?' in parts else (parts, '')
                
                params = parse_qs(body)
                message = params.get('body', [''])[0]
            else:
                phone = content
                message = ''
            
            return {
                "type": "sms",
                "data": {
                    "phone": phone,
                    "message": message
                }
            }
            
        except Exception:
            return {
                "type": "sms",
                "data": {"content": content}
            }
    
    def _parse_structured_text(self, content: str) -> Dict:
        """Parse structured text content"""
        try:
            # Look for common patterns
            structured_data = {}
            
            # ID patterns
            id_patterns = [
                r'ID:\s*(\w+)',
                r'Ref:\s*(\w+)',
                r'Ticket:\s*(\w+)',
                r'Order:\s*(\w+)'
            ]
            
            for pattern in id_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    structured_data['id'] = match.group(1)
                    break
            
            # Date patterns
            date_pattern = r'(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})'
            date_match = re.search(date_pattern, content)
            if date_match:
                structured_data['date'] = date_match.group(1)
            
            # Amount patterns
            amount_pattern = r'\$?(\d+(?:\.\d{2})?)'
            amount_matches = re.findall(amount_pattern, content)
            if amount_matches:
                structured_data['amounts'] = amount_matches
            
            return {
                "type": "structured_text",
                "data": {
                    "content": content,
                    "extracted_data": structured_data
                }
            }
            
        except Exception:
            return {
                "type": "text",
                "data": {"content": content}
            }
    
    def _detect_data_type(self, content: str) -> str:
        """Detect the type of data in QR code"""
        content_lower = content.lower()
        
        if content.startswith(('http://', 'https://', 'www.')):
            return 'url'
        elif content.startswith('mailto:') or '@' in content:
            return 'email'
        elif content.startswith(('tel:', 'phone:', 'call:')):
            return 'phone'
        elif content.startswith(('sms:', 'smsto:')):
            return 'sms'
        elif content.startswith(('wifi:', 'WiFi:')):
            return 'wifi'
        elif content.startswith('begin:vcard'):
            return 'vcard'
        elif content.startswith('geo:'):
            return 'location'
        elif re.match(r'^[a-f0-9]{32,}$', content_lower):
            return 'hash'
        elif re.match(r'^\d+$', content):
            return 'number'
        else:
            return 'text'
    
    def _is_phone_number(self, content: str) -> bool:
        """Check if content looks like a phone number"""
        # Remove common phone number characters
        cleaned = re.sub(r'[^\d+]', '', content)
        # Phone numbers are typically 10-15 digits
        return 10 <= len(cleaned) <= 15 and cleaned.startswith(('+', '1', '2', '3', '4', '5', '6', '7', '8', '9'))
    
    def _is_coordinates(self, content: str) -> bool:
        """Check if content looks like geographic coordinates"""
        # Pattern for latitude, longitude
        coord_pattern = r'^-?\d+\.?\d*,\s*-?\d+\.?\d*$'
        return bool(re.match(coord_pattern, content))
    
    def _is_structured_text(self, content: str) -> bool:
        """Check if content has structured data patterns"""
        patterns = [
            r'ID:\s*\w+',
            r'Ref:\s*\w+',
            r'Ticket:\s*\w+',
            r'\d{4}-\d{2}-\d{2}',
            r'\$\d+\.\d{2}'
        ]
        
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)
    
    def _format_phone_number(self, phone: str) -> str:
        """Format phone number for display"""
        try:
            # Remove non-digit characters except +
            cleaned = re.sub(r'[^\d+]', '', phone)
            
            # Basic formatting for US numbers
            if len(cleaned) == 10 and not cleaned.startswith('+'):
                return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
            elif len(cleaned) == 11 and cleaned.startswith('1'):
                return f"+1 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"
            else:
                return cleaned
                
        except Exception:
            return phone
    
    def get_statistics(self) -> Dict:
        """Get QR scanner service statistics"""
        try:
            total_items = LostFoundItem.objects.count()
            scanned_items = LostFoundItem.objects.filter(
                qr_data__isnull=False
            ).count()
            
            qr_found_count = LostFoundItem.objects.filter(
                qr_data__isnull=False,
                qr_data__codes_found__gt=0
            ).count()
            
            return {
                "total_items": total_items,
                "scanned_items": scanned_items,
                "qr_found_count": qr_found_count,
                "qr_found_rate": (qr_found_count / scanned_items * 100) if scanned_items > 0 else 0,
                "scanning_rate": (scanned_items / total_items * 100) if total_items > 0 else 0,
                "pyzbar_available": self.pyzbar_available,
                "supported_types": self.supported_types
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_items": 0,
                "scanned_items": 0
            }


# Singleton instance
_qr_scanner_service = None

def get_qr_scanner_service():
    """Get singleton instance of QRScannerService"""
    global _qr_scanner_service
    if _qr_scanner_service is None:
        _qr_scanner_service = QRScannerService()
    return _qr_scanner_service
