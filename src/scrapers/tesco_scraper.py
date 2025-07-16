"""
Tesco-specific scraper implementation.
"""

import json
import logging
import time
from typing import Dict, Any
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class TescoScraper(BaseScraper):
    """Specialized scraper for Tesco website."""
    
    async def scrape_product(self, url: str, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape product from Tesco with specific handling."""
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
                
            # Tesco-specific wait for content
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            
            # Handle cookie consent if present
            await self._handle_cookie_consent()
            
            # Wait for price elements
            price_selectors = [
                '[data-testid="price-details"] .value',
                '.price-per-sellable-unit .value',
                '.price-current',
                '.beans-price__text'
            ]
            
            await self.wait_for_selectors(price_selectors, timeout=10000)
            
            # Extract price with Tesco-specific logic
            price = await self._extract_tesco_price()
            result['price'] = price
            
            # Check availability
            is_available, availability_text = await self._check_tesco_availability()
            result['in_stock'] = is_available
            result['availability_text'] = availability_text
            
            # Extract product title
            title = await self._extract_tesco_title()
            result['product_title'] = title
            
            # Extract additional Tesco-specific data
            raw_data = await self._extract_tesco_metadata()
            result['raw_data'] = {
                'url': url,
                'tesco_metadata': raw_data,
                'user_agent': await self.page.evaluate('navigator.userAgent')
            }
            
            result['success'] = price is not None
            
        except Exception as e:
            logger.error(f"Error scraping Tesco product {url}: {str(e)}")
            result['error'] = str(e)
            
        finally:
            result['response_time'] = time.time() - start_time
            
        return result
        
    async def _handle_cookie_consent(self):
        """Handle Tesco cookie consent popup."""
        try:
            # Look for cookie consent buttons
            cookie_selectors = [
                '[data-testid="cookie-consent-accept"]',
                '#accept-cookies',
                '.cookie-consent-accept',
                'button[aria-label*="Accept"]'
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
            logger.debug(f"Cookie consent handling failed: {str(e)}")
            
    async def _extract_tesco_price(self) -> float:
        """Extract price using Tesco-specific selectors."""
        price_selectors = [
            '[data-testid="price-details"] .value',
            '.price-per-sellable-unit .value',
            '.price-current .value',
            '.beans-price__text',
            '.price-per-quantity-weight .value'
        ]
        
        for selector in price_selectors:
            try:
                price_text = await self.extract_text_by_selector(selector)
                if price_text:
                    price = self.parse_price(price_text)
                    if price:
                        return price
            except Exception:
                continue
                
        # Try alternative extraction method
        try:
            price_element = await self.page.query_selector('[data-testid="price-details"]')
            if price_element:
                price_text = await price_element.text_content()
                if price_text:
                    price = self.parse_price(price_text)
                    if price:
                        return price
        except Exception:
            pass
            
        return None
        
    async def _check_tesco_availability(self) -> tuple[bool, str]:
        """Check availability using Tesco-specific selectors."""
        availability_selectors = [
            '[data-testid="product-availability"]',
            '.product-availability',
            '.availability-message',
            '.stock-status'
        ]
        
        for selector in availability_selectors:
            availability_text = await self.extract_text_by_selector(selector)
            if availability_text:
                availability_lower = availability_text.lower()
                
                # Tesco-specific availability indicators
                if any(indicator in availability_lower for indicator in [
                    'out of stock', 'unavailable', 'not available',
                    'temporarily unavailable', 'sold out'
                ]):
                    return False, availability_text
                elif any(indicator in availability_lower for indicator in [
                    'in stock', 'available', 'add to basket'
                ]):
                    return True, availability_text
                    
        # Check for add to basket button as availability indicator
        try:
            add_to_basket = await self.page.query_selector('[data-testid="add-to-trolley"]')
            if add_to_basket:
                is_disabled = await add_to_basket.is_disabled()
                return not is_disabled, "Available" if not is_disabled else "Unavailable"
        except Exception:
            pass
            
        return True, "Unknown"  # Default to available
        
    async def _extract_tesco_title(self) -> str:
        """Extract product title using Tesco-specific selectors."""
        title_selectors = [
            '[data-testid="product-title"]',
            '.product-title h1',
            '.product-details-tile h1',
            'h1[data-testid="product-title"]'
        ]
        
        for selector in title_selectors:
            title = await self.extract_text_by_selector(selector)
            if title:
                return title
                
        return None
        
    async def _extract_tesco_metadata(self) -> Dict[str, Any]:
        """Extract additional Tesco-specific metadata."""
        metadata = {}
        
        try:
            # Extract product ID if available
            product_id_element = await self.page.query_selector('[data-testid="product-id"]')
            if product_id_element:
                metadata['product_id'] = await product_id_element.text_content()
                
            # Extract brand information
            brand_element = await self.page.query_selector('.product-brand')
            if brand_element:
                metadata['brand'] = await brand_element.text_content()
                
            # Extract pack size information
            pack_size_element = await self.page.query_selector('.product-pack-size')
            if pack_size_element:
                metadata['pack_size'] = await pack_size_element.text_content()
                
            # Extract any promotional information
            promo_elements = await self.page.query_selector_all('.promotion-message')
            if promo_elements:
                promotions = []
                for promo in promo_elements:
                    promo_text = await promo.text_content()
                    if promo_text:
                        promotions.append(promo_text.strip())
                metadata['promotions'] = promotions
                
        except Exception as e:
            logger.debug(f"Error extracting Tesco metadata: {str(e)}")
            
        return metadata