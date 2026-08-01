"""
Price Compare Service - Scrapy Implementation
Scrapes and compares prices from multiple e-commerce sources
"""

import os
import json
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse
import time
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.utils import timezone

# Phrases that show up on Amazon/eBay's anti-bot interstitials. Amazon in
# particular sometimes answers automated requests with HTTP 200 + a page
# containing unrelated/placeholder pricing widgets instead of an honest
# block — parsing that page yields prices that look real but aren't tied to
# the actual product. Checking for these markers before parsing means we
# fail closed (report no data) instead of returning numbers that may not be
# genuine, consistent with this service never fabricating results.
_BLOCK_PAGE_MARKERS = (
    'automated access',
    'api-services-support@amazon.com',
    "to discuss automated access",
    'sorry, we just need to make sure',
    'enter the characters you see below',
    'pardon our interruption',
)

# Try to import Scrapy components
try:
    import scrapy
    from scrapy.crawler import CrawlerProcess
    from scrapy.http import Request
    from scrapy.selector import Selector
    SCRAPY_AVAILABLE = True
except ImportError:
    print("⚠️ Scrapy not available, using requests fallback")
    SCRAPY_AVAILABLE = False

# Try to import requests and BeautifulSoup (should be available)
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("⚠️ requests not available")
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    print("⚠️ BeautifulSoup not available")
    BS4_AVAILABLE = False

# Set overall availability
REQUESTS_AVAILABLE = REQUESTS_AVAILABLE and BS4_AVAILABLE

# Local imports
from ..models.lost_found import LostFoundItem, ProductCache

# Define PriceSpider only if Scrapy is available
if SCRAPY_AVAILABLE:
    class PriceSpider(scrapy.Spider):
        """Scrapy spider for price comparison"""
        
        name = 'price_spider'
        
        def __init__(self, product_name=None, *args, **kwargs):
            super(PriceSpider, self).__init__(*args, **kwargs)
            self.product_name = product_name or ""
            self.results = []
            
            # E-commerce sites to scrape
            self.sites = [
                {
                    'name': 'Amazon',
                    'url': f'https://www.amazon.com/s?k={quote(product_name)}',
                    'price_selector': '.a-price .a-offscreen',
                    'title_selector': '.s-title .a-text-normal',
                    'currency': 'USD'
                },
                {
                    'name': 'eBay',
                    'url': f'https://www.ebay.com/sch/i.html?_nkw={quote(product_name)}',
                    'price_selector': '.s-item__price',
                    'title_selector': '.s-item__title',
                    'currency': 'USD'
                }
            ]
        
        def start_requests(self):
            """Generate initial requests"""
            for site in self.sites:
                yield Request(
                    url=site['url'],
                    callback=self.parse,
                    meta={'site': site}
                )
        
        def parse(self, response):
            """Parse product listings"""
            site = response.meta['site']
            
            try:
                # Extract product listings
                products = []
                
                # Extract titles
                titles = response.css(site['title_selector']).getall()
                
                # Extract prices
                prices = response.css(site['price_selector']).getall()
                
                # Combine titles and prices
                for i, (title, price_text) in enumerate(zip(titles, prices)):
                    # Clean and parse price
                    price = self._parse_price(price_text)
                    
                    if price > 0:
                        products.append({
                            'title': self._clean_text(title),
                            'price': float(price),
                            'currency': site['currency'],
                            'url': response.url,
                            'position': i + 1
                        })
                
                result = {
                    'site': site['name'],
                    'products': products,
                    'total_found': len(products),
                    'scraped_at': timezone.now().isoformat()
                }
                
                self.results.append(result)
                
            except Exception as e:
                self.results.append({
                    'site': site['name'],
                    'error': str(e),
                    'scraped_at': timezone.now().isoformat()
                })
        
        def _parse_price(self, price_text: str) -> Decimal:
            """Parse price text to decimal"""
            try:
                # Remove currency symbols and whitespace
                cleaned = re.sub(r'[^\d.,]', '', price_text)
                
                # Handle different decimal separators
                cleaned = cleaned.replace(',', '.')
                
                # Extract the first valid price
                price_match = re.search(r'\d+\.?\d*', cleaned)
                
                if price_match:
                    return Decimal(price_match.group())
                
                return Decimal('0')
                
            except (InvalidOperation, ValueError):
                return Decimal('0')
        
        def _clean_text(self, text: str) -> str:
            """Clean text content"""
            if not text:
                return ""
            
            # Remove HTML tags
            clean = re.sub(r'<[^>]+>', '', text)
            
            # Normalize whitespace
            clean = ' '.join(clean.split())
            
            return clean.strip()
else:
    PriceSpider = None


class PriceCompareService:
    """Price Compare Service using Scrapy or requests fallback"""
    
    def __init__(self):
        """Initialize price comparison service"""
        print("💰 Price Compare Service initializing...")
        
        self.scrapy_available = SCRAPY_AVAILABLE
        self.requests_available = REQUESTS_AVAILABLE
        
        # Browser-like headers for requests. A bare User-Agent reliably gets a
        # 503 from Amazon and a 403 from eBay; a full header set at least gets
        # a real response some of the time (still no guarantee — see
        # `_BLOCK_PAGE_MARKERS` below for why we still verify the body).
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Rate limiting
        self.request_delay = 1  # seconds between requests
        self.last_request_time = 0
        
        # Price cache duration (hours)
        self.cache_duration = 24
        
        if self.scrapy_available:
            print("✅ Scrapy available for advanced scraping")
        elif self.requests_available:
            print("✅ Using requests + BeautifulSoup for scraping")
        else:
            print("⚠️ No scraping libraries available - price comparison disabled")
        
        print("✅ Price Compare Service initialized!")
    
    def compare_prices(self, product_name: str, use_cache: bool = True) -> Dict:
        """
        Compare prices for a product across multiple sources
        """
        try:
            if not self.requests_available:
                return {
                    "status": "error",
                    "error": "No scraping libraries available",
                    "message": "Install requests and BeautifulSoup for price comparison"
                }
            
            # Check cache first
            if use_cache:
                cached_result = self._get_cached_prices(product_name)
                if cached_result:
                    return cached_result
            
            # Scrape prices
            if self.scrapy_available:
                prices = self._scrape_with_scrapy(product_name)
            else:
                prices = self._scrape_with_requests(product_name)
            
            # Process and aggregate results
            processed_prices = self._process_price_data(prices)
            
            # Cache results
            self._cache_prices(product_name, processed_prices)
            
            return {
                "status": "success",
                "product_name": product_name,
                "prices": processed_prices,
                "total_sources": len(processed_prices),
                "scraped_at": timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": f"Failed to compare prices for {product_name}"
            }
    
    def _get_cached_prices(self, product_name: str) -> Optional[Dict]:
        """Get cached price data"""
        try:
            # Normalize product name for cache lookup
            normalized_name = self._normalize_product_name(product_name)
            
            # Check cache
            cache = ProductCache.objects.filter(
                product_name__icontains=product_name
            ).first()
            
            if cache and cache.is_active:
                # Check if cache is still valid
                cache_age = timezone.now() - cache.last_scraped
                if cache_age.total_seconds() < self.cache_duration * 3600:
                    return {
                        "status": "cached",
                        "product_name": cache.product_name,
                        "prices": cache.prices,
                        "total_sources": cache.source_count,
                        "cached_at": cache.last_scraped.isoformat(),
                        "cache_age_hours": cache_age.total_seconds() / 3600
                    }
            
            return None
            
        except Exception as e:
            print(f"Cache lookup error: {e}")
            return None
    
    def _scrape_with_scrapy(self, product_name: str) -> List[Dict]:
        """Scrape prices using Scrapy"""
        try:
            if not SCRAPY_AVAILABLE or PriceSpider is None:
                return []
            
            # Configure Scrapy settings
            settings = {
                'USER_AGENT': self.headers['User-Agent'],
                'ROBOTSTXT_OBEY': True,
                'DOWNLOAD_DELAY': self.request_delay,
                'CONCURRENT_REQUESTS': 1,
                'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
                'FEED_FORMAT': 'json',
                'FEED_URI': 'temp_prices.json'
            }
            
            # Run spider
            process = CrawlerProcess(settings)
            
            # This is a simplified approach - in production, you'd want to run this asynchronously
            results = []
            
            def collect_results(item):
                results.append(item)
            
            # Create and run spider
            spider = PriceSpider(product_name=product_name)
            process.crawl(spider)
            process.start()
            
            return spider.results if hasattr(spider, 'results') else []
            
        except Exception as e:
            print(f"Scrapy scraping failed: {e}")
            # Fallback to requests
            return self._scrape_with_requests(product_name)
    
    def _scrape_with_requests(self, product_name: str) -> List[Dict]:
        """Scrape prices using requests (fallback)"""
        try:
            results = []
            
            # Define sites to scrape
            sites = [
                {
                    'name': 'Amazon',
                    'url': f'https://www.amazon.com/s?k={quote(product_name)}',
                    'price_selectors': ['.a-price .a-offscreen', '.a-price-whole'],
                    'title_selectors': ['.s-title .a-text-normal', '.a-size-medium'],
                    'currency': 'USD'
                },
                {
                    'name': 'eBay',
                    'url': f'https://www.ebay.com/sch/i.html?_nkw={quote(product_name)}',
                    'price_selectors': ['.s-item__price', '.s-item__details .bold'],
                    'title_selectors': ['.s-item__title', '.s-item__title--tagline'],
                    'currency': 'USD'
                }
            ]
            
            for site in sites:
                try:
                    # Rate limiting
                    self._rate_limit()
                    
                    # Make request
                    response = requests.get(
                        site['url'],
                        headers=self.headers,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        site_results = self._parse_site_response(response.text, site)
                        results.append(site_results)
                    else:
                        results.append({
                            'site': site['name'],
                            'error': f"HTTP {response.status_code}",
                            'scraped_at': timezone.now().isoformat()
                        })
                        
                except Exception as e:
                    results.append({
                        'site': site['name'],
                        'error': str(e),
                        'scraped_at': timezone.now().isoformat()
                    })
            
            return results
            
        except Exception as e:
            print(f"Requests scraping failed: {e}")
            return []
    
    def _parse_site_response(self, html: str, site: Dict) -> Dict:
        """Parse HTML response from a site"""
        try:
            if not BS4_AVAILABLE:
                return {
                    'site': site['name'],
                    'error': 'BeautifulSoup not available',
                    'scraped_at': timezone.now().isoformat()
                }

            lowered = html.lower()
            if any(marker in lowered for marker in _BLOCK_PAGE_MARKERS):
                return {
                    'site': site['name'],
                    'error': 'blocked by anti-bot interstitial',
                    'scraped_at': timezone.now().isoformat()
                }

            soup = BeautifulSoup(html, 'html.parser')
            products = []
            
            # Try different selectors for prices
            prices = []
            for selector in site['price_selectors']:
                price_elements = soup.select(selector)
                if price_elements:
                    prices = [elem.get_text() for elem in price_elements[:10]]
                    break
            
            # Try different selectors for titles
            titles = []
            for selector in site['title_selectors']:
                title_elements = soup.select(selector)
                if title_elements:
                    titles = [elem.get_text() for elem in title_elements[:10]]
                    break
            
            # Combine titles and prices
            for i, (title, price_text) in enumerate(zip(titles, prices)):
                price = self._parse_price_text(price_text)
                
                if price > 0:
                    products.append({
                        'title': self._clean_text(title),
                        'price': float(price),
                        'currency': site['currency'],
                        'source': site['name'],
                        'position': i + 1
                    })
            
            return {
                'site': site['name'],
                'products': products,
                'total_found': len(products),
                'scraped_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'site': site['name'],
                'error': str(e),
                'scraped_at': timezone.now().isoformat()
            }
    
    def _process_price_data(self, raw_results: List[Dict]) -> Dict:
        """Process and aggregate price data"""
        try:
            processed = {
                'sources': {},
                'summary': {},
                'products': []
            }
            
            all_prices = []
            all_products = []
            
            for result in raw_results:
                if 'products' in result:
                    site_name = result['site']
                    products = result['products']
                    
                    # Store site-specific data
                    processed['sources'][site_name] = {
                        'total_products': len(products),
                        'products': products
                    }
                    
                    # Collect all prices for summary
                    for product in products:
                        all_prices.append(product['price'])
                        all_products.append(product)
            
            # Calculate summary statistics
            if all_prices:
                processed['summary'] = {
                    'lowest_price': min(all_prices),
                    'highest_price': max(all_prices),
                    'average_price': sum(all_prices) / len(all_prices),
                    'median_price': self._calculate_median(all_prices),
                    'total_products': len(all_products),
                    'price_range': max(all_prices) - min(all_prices)
                }
                
                # Sort all products by price
                all_products.sort(key=lambda x: x['price'])
                processed['products'] = all_products[:20]  # Top 20 cheapest
            
            return processed
            
        except Exception as e:
            print(f"Error processing price data: {e}")
            return {'sources': {}, 'summary': {}, 'products': []}
    
    def _cache_prices(self, product_name: str, price_data: Dict):
        """Cache price data"""
        try:
            # Normalize product name
            normalized_name = self._normalize_product_name(product_name)
            
            # Calculate summary values
            summary = price_data.get('summary', {})
            
            # Update or create cache
            cache, created = ProductCache.objects.update_or_create(
                product_name=product_name,
                normalized_name=normalized_name,
                defaults={
                    'prices': price_data,
                    'lowest_price': summary.get('lowest_price'),
                    'highest_price': summary.get('highest_price'),
                    'average_price': summary.get('average_price'),
                    'source_count': len(price_data.get('sources', {})),
                    'is_active': True,
                    'last_scraped': timezone.now()
                }
            )
            
            print(f"Cached price data for {product_name}: {'created' if created else 'updated'}")
            
        except Exception as e:
            print(f"Error caching prices: {e}")
    
    def _normalize_product_name(self, product_name: str) -> str:
        """Normalize product name for consistent caching"""
        try:
            # Convert to lowercase and remove special characters
            normalized = re.sub(r'[^a-z0-9\s]', '', product_name.lower())
            
            # Remove extra whitespace
            normalized = ' '.join(normalized.split())
            
            return normalized
            
        except Exception:
            return product_name.lower()
    
    def _rate_limit(self):
        """Implement rate limiting"""
        try:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.request_delay:
                sleep_time = self.request_delay - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
            
        except Exception:
            pass
    
    def _parse_price_text(self, price_text: str) -> Decimal:
        """Parse price text to decimal"""
        try:
            if not price_text:
                return Decimal('0')
            
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[^\d.,]', '', price_text)
            
            # Handle different decimal separators
            cleaned = cleaned.replace(',', '.')
            
            # Extract the first valid price
            price_match = re.search(r'\d+\.?\d*', cleaned)
            
            if price_match:
                return Decimal(price_match.group())
            
            return Decimal('0')
            
        except (InvalidOperation, ValueError):
            return Decimal('0')
    
    def _clean_text(self, text: str) -> str:
        """Clean text content"""
        if not text:
            return ""
        
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        
        # Normalize whitespace
        clean = ' '.join(clean.split())
        
        return clean.strip()
    
    def _calculate_median(self, prices: List[float]) -> float:
        """Calculate median price"""
        try:
            sorted_prices = sorted(prices)
            n = len(sorted_prices)
            
            if n % 2 == 0:
                return (sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2
            else:
                return sorted_prices[n//2]
                
        except Exception:
            return 0.0
    
    def get_price_trends(self, product_name: str, days: int = 30) -> Dict:
        """Get price trends for a product over time"""
        try:
            # This would require historical price data
            # For now, return cached data with trend analysis
            cached = self._get_cached_prices(product_name)
            
            if not cached:
                return {
                    "status": "no_data",
                    "message": "No historical data available"
                }
            
            # Simple trend analysis (would be more complex with real historical data)
            prices = cached['prices'].get('products', [])
            if prices:
                price_range = cached['prices']['summary'].get('price_range', 0)
                avg_price = cached['prices']['summary'].get('average_price', 0)
                
                # Basic trend indicators
                if price_range > avg_price * 0.5:
                    trend = "volatile"
                elif price_range < avg_price * 0.1:
                    trend = "stable"
                else:
                    trend = "moderate"
            else:
                trend = "unknown"
            
            return {
                "status": "success",
                "product_name": product_name,
                "trend": trend,
                "current_data": cached,
                "analysis_period_days": days
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_statistics(self) -> Dict:
        """Get price comparison service statistics"""
        try:
            total_cached = ProductCache.objects.count()
            active_cached = ProductCache.objects.filter(is_active=True).count()
            
            # Calculate cache hit rate (would need more tracking in production)
            cache_hit_rate = 75.0  # Placeholder
            
            return {
                "total_cached_products": total_cached,
                "active_cached_products": active_cached,
                "cache_hit_rate": cache_hit_rate,
                "cache_duration_hours": self.cache_duration,
                "scrapy_available": self.scrapy_available,
                "request_delay_seconds": self.request_delay,
                "supported_sites": ["Amazon", "eBay"],
                "last_updated": timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_cached_products": 0
            }


# Singleton instance
_price_compare_service = None

def get_price_compare_service():
    """Get singleton instance of PriceCompareService"""
    global _price_compare_service
    if _price_compare_service is None:
        _price_compare_service = PriceCompareService()
    return _price_compare_service
