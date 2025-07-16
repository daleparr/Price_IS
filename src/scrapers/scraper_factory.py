"""
Factory class for creating retailer-specific scrapers.
"""

import logging
from typing import Dict, Any, Type
from .base_scraper import BaseScraper, GenericScraper
from .tesco_scraper import TescoScraper

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Factory for creating appropriate scraper instances."""
    
    # Registry of retailer-specific scrapers
    SCRAPER_REGISTRY: Dict[str, Type[BaseScraper]] = {
        'tesco_scraper': TescoScraper,
        'generic_scraper': GenericScraper,
    }
    
    @classmethod
    def create_scraper(cls, retailer_config: Dict[str, Any], settings: Dict[str, Any]) -> BaseScraper:
        """Create appropriate scraper instance for retailer."""
        scraper_module = retailer_config.get('scraper_module', 'generic_scraper')
        
        # Get scraper class from registry
        scraper_class = cls.SCRAPER_REGISTRY.get(scraper_module)
        
        if not scraper_class:
            logger.warning(f"Unknown scraper module '{scraper_module}', using generic scraper")
            scraper_class = GenericScraper
            
        logger.info(f"Creating {scraper_class.__name__} for {retailer_config['name']}")
        return scraper_class(retailer_config, settings)
        
    @classmethod
    def register_scraper(cls, module_name: str, scraper_class: Type[BaseScraper]):
        """Register a new scraper class."""
        cls.SCRAPER_REGISTRY[module_name] = scraper_class
        logger.info(f"Registered scraper: {module_name} -> {scraper_class.__name__}")
        
    @classmethod
    def get_available_scrapers(cls) -> Dict[str, str]:
        """Get list of available scrapers."""
        return {
            module: scraper_class.__name__ 
            for module, scraper_class in cls.SCRAPER_REGISTRY.items()
        }


# Additional retailer scrapers can be added here
class SainsburysScraper(BaseScraper):
    """Sainsbury's-specific scraper implementation."""
    
    async def scrape_product(self, url: str, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape product from Sainsbury's with specific handling."""
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
                
            # Sainsbury's-specific wait
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            
            # Handle cookie consent
            await self._handle_sainsburys_cookie_consent()
            
            # Wait for price elements
            price_selectors = [
                '.pd__cost__retail-price',
                '.pricing__now-price',
                '.price-current'
            ]
            
            await self.wait_for_selectors(price_selectors, timeout=10000)
            
            # Extract price
            price = await self._extract_sainsburys_price()
            result['price'] = price
            
            # Check availability
            is_available, availability_text = await self._check_sainsburys_availability()
            result['in_stock'] = is_available
            result['availability_text'] = availability_text
            
            # Extract product title
            title = await self._extract_sainsburys_title()
            result['product_title'] = title
            
            result['raw_data'] = {
                'url': url,
                'user_agent': await self.page.evaluate('navigator.userAgent')
            }
            
            result['success'] = price is not None
            
        except Exception as e:
            logger.error(f"Error scraping Sainsbury's product {url}: {str(e)}")
            result['error'] = str(e)
            
        finally:
            result['response_time'] = time.time() - start_time
            
        return result
        
    async def _handle_sainsburys_cookie_consent(self):
        """Handle Sainsbury's cookie consent."""
        try:
            cookie_selectors = [
                '#onetrust-accept-btn-handler',
                '.cookie-accept-button',
                '[data-testid="cookie-accept"]'
            ]
            
            for selector in cookie_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        await element.click()
                        await self.random_delay(1, 2)
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Sainsbury's cookie consent handling failed: {str(e)}")
            
    async def _extract_sainsburys_price(self) -> float:
        """Extract price using Sainsbury's-specific selectors."""
        price_selectors = [
            '.pd__cost__retail-price',
            '.pricing__now-price',
            '.price-current',
            '.product-price .price'
        ]
        
        for selector in price_selectors:
            price_text = await self.extract_text_by_selector(selector)
            if price_text:
                price = self.parse_price(price_text)
                if price:
                    return price
                    
        return None
        
    async def _check_sainsburys_availability(self) -> tuple[bool, str]:
        """Check availability using Sainsbury's-specific selectors."""
        availability_selectors = [
            '.pd__cost__availability',
            '.availability-message',
            '.stock-status'
        ]
        
        for selector in availability_selectors:
            availability_text = await self.extract_text_by_selector(selector)
            if availability_text:
                availability_lower = availability_text.lower()
                
                if any(indicator in availability_lower for indicator in [
                    'out of stock', 'unavailable', 'not available'
                ]):
                    return False, availability_text
                elif any(indicator in availability_lower for indicator in [
                    'in stock', 'available'
                ]):
                    return True, availability_text
                    
        return True, "Unknown"
        
    async def _extract_sainsburys_title(self) -> str:
        """Extract product title using Sainsbury's-specific selectors."""
        title_selectors = [
            '.pd__header__title',
            '.product-title h1',
            'h1.product-name'
        ]
        
        for selector in title_selectors:
            title = await self.extract_text_by_selector(selector)
            if title:
                return title
                
        return None


# Register additional scrapers
ScraperFactory.register_scraper('sainsburys_scraper', SainsburysScraper)