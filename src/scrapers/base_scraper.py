"""
Base scraper class with Playwright integration and stealth capabilities.
"""

import asyncio
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all retailer scrapers."""
    
    def __init__(self, retailer_config: Dict[str, Any], settings: Dict[str, Any]):
        self.retailer_config = retailer_config
        self.settings = settings
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.user_agent_generator = UserAgent()
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.setup_browser()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
        
    async def setup_browser(self):
        """Initialize Playwright browser with stealth settings."""
        playwright = await async_playwright().start()
        
        # Browser launch options for stealth
        launch_options = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-client-side-phishing-detection',
                '--disable-component-extensions-with-background-pages',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-features=TranslateUI',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--disable-sync',
                '--force-color-profile=srgb',
                '--metrics-recording-only',
                '--no-default-browser-check',
                '--no-first-run',
                '--password-store=basic',
                '--use-mock-keychain',
                '--disable-blink-features=AutomationControlled'
            ]
        }
        
        self.browser = await playwright.chromium.launch(**launch_options)
        
        # Create context with stealth settings
        context_options = {
            'viewport': {'width': 1366, 'height': 768},
            'user_agent': self.get_random_user_agent(),
            'locale': 'en-GB',
            'timezone_id': 'Europe/London',
            'permissions': [],
            'extra_http_headers': {
                'Accept-Language': 'en-GB,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        }
        
        self.context = await self.browser.new_context(**context_options)
        
        # Add stealth scripts
        await self.context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-GB', 'en'],
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        self.page = await self.context.new_page()
        
        # Set additional page properties
        await self.page.set_extra_http_headers({
            'sec-ch-ua': '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
        })
        
        logger.info(f"Browser setup completed for {self.retailer_config['name']}")
        
    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        try:
            return self.user_agent_generator.random
        except Exception:
            # Fallback user agents
            fallback_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            ]
            return random.choice(fallback_agents)
            
    async def random_delay(self, min_seconds: float = None, max_seconds: float = None):
        """Add random delay to mimic human behavior."""
        min_delay = min_seconds or self.settings.get('default_delay_min', 2)
        max_delay = max_seconds or self.settings.get('default_delay_max', 8)
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
        
    async def navigate_to_url(self, url: str) -> bool:
        """Navigate to URL with error handling and retries."""
        max_retries = self.settings.get('max_retries', 3)
        timeout = self.settings.get('request_timeout', 30) * 1000  # Convert to milliseconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Navigating to {url} (attempt {attempt + 1})")
                
                # Navigate with timeout
                response = await self.page.goto(
                    url, 
                    wait_until='domcontentloaded',
                    timeout=timeout
                )
                
                if response and response.status < 400:
                    # Wait for page to stabilize
                    await self.random_delay(1, 3)
                    return True
                else:
                    logger.warning(f"HTTP {response.status if response else 'No response'} for {url}")
                    
            except Exception as e:
                logger.error(f"Navigation attempt {attempt + 1} failed for {url}: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    await asyncio.sleep(wait_time)
                    
        return False
        
    async def wait_for_selectors(self, selectors: List[str], timeout: int = 10000) -> bool:
        """Wait for any of the provided selectors to appear."""
        try:
            for selector in selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=timeout)
                    return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"Error waiting for selectors {selectors}: {str(e)}")
            return False
            
    async def extract_text_by_selector(self, selector: str) -> Optional[str]:
        """Extract text content by CSS selector."""
        try:
            element = await self.page.query_selector(selector)
            if element:
                text = await element.text_content()
                return text.strip() if text else None
        except Exception as e:
            logger.debug(f"Could not extract text for selector '{selector}': {str(e)}")
        return None
        
    async def extract_price(self, selectors: Dict[str, str]) -> Optional[float]:
        """Extract price using multiple selector strategies."""
        price_selectors = [
            selectors.get('price'),
            selectors.get('price_alt'),
        ]
        
        for selector in price_selectors:
            if not selector:
                continue
                
            price_text = await self.extract_text_by_selector(selector)
            if price_text:
                price = self.parse_price(price_text)
                if price:
                    return price
                    
        return None
        
    def parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from text string."""
        if not price_text:
            return None
            
        # Remove common currency symbols and whitespace
        cleaned = price_text.replace('£', '').replace('$', '').replace(',', '').strip()
        
        # Extract numeric value
        import re
        price_match = re.search(r'(\d+\.?\d*)', cleaned)
        if price_match:
            try:
                return float(price_match.group(1))
            except ValueError:
                pass
                
        return None
        
    async def check_availability(self, selectors: Dict[str, str]) -> tuple[bool, str]:
        """Check product availability."""
        availability_selector = selectors.get('availability')
        if not availability_selector:
            return True, "Unknown"  # Assume available if no selector
            
        availability_text = await self.extract_text_by_selector(availability_selector)
        if not availability_text:
            return True, "Unknown"
            
        availability_lower = availability_text.lower()
        
        # Common out of stock indicators
        out_of_stock_indicators = [
            'out of stock', 'unavailable', 'not available', 'sold out',
            'temporarily unavailable', 'currently unavailable'
        ]
        
        is_available = not any(indicator in availability_lower for indicator in out_of_stock_indicators)
        return is_available, availability_text
        
    @abstractmethod
    async def scrape_product(self, url: str, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """Abstract method to scrape product data. Must be implemented by subclasses."""
        pass
        
    async def cleanup(self):
        """Clean up browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")


class GenericScraper(BaseScraper):
    """Generic scraper implementation for retailers without specific customizations."""
    
    async def scrape_product(self, url: str, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape product using generic selectors."""
        start_time = time.time()
        result = {
            'success': False,
            'price': None,
            'in_stock': None,
            'availability_text': None,
            'product_title': None,
            'error': None,
            'response_time': None,
            'scraped_at': time.time(),
            'raw_data': {}
        }
        
        try:
            # Navigate to product page
            if not await self.navigate_to_url(url):
                result['error'] = 'Failed to navigate to URL'
                return result
                
            # Parse selectors from retailer config
            selectors = json.loads(self.retailer_config.get('selectors', '{}'))
            wait_selectors = json.loads(self.retailer_config.get('wait_selectors', '[]'))
            
            # Wait for key elements to load
            if wait_selectors:
                await self.wait_for_selectors(wait_selectors)
                
            # Extract price
            price = await self.extract_price(selectors)
            result['price'] = price
            
            # Check availability
            is_available, availability_text = await self.check_availability(selectors)
            result['in_stock'] = is_available
            result['availability_text'] = availability_text
            
            # Extract product title
            title_selector = selectors.get('product_title')
            if title_selector:
                result['product_title'] = await self.extract_text_by_selector(title_selector)
                
            # Store raw data
            result['raw_data'] = {
                'url': url,
                'selectors_used': selectors,
                'user_agent': await self.page.evaluate('navigator.userAgent')
            }
            
            result['success'] = price is not None
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            result['error'] = str(e)
            
        finally:
            result['response_time'] = time.time() - start_time
            
        return result