"""
Data validation and cleaning utilities for price tracker.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


class PriceValidator:
    """Validates and cleans price data."""
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.min_price = 0.01  # Minimum valid price
        self.max_price = 1000.0  # Maximum valid price for OTC medicines
        
    def validate_price_data(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate and clean scraped price data.
        
        Returns:
            Tuple of (is_valid, cleaned_data)
        """
        cleaned_data = data.copy()
        validation_errors = []
        
        # Validate price
        price_valid, cleaned_price, price_error = self._validate_price(data.get('price'))
        if not price_valid:
            validation_errors.append(f"Price validation failed: {price_error}")
        cleaned_data['price'] = cleaned_price
        
        # Validate availability
        availability_valid, cleaned_availability = self._validate_availability(
            data.get('in_stock'), 
            data.get('availability_text')
        )
        if not availability_valid:
            validation_errors.append("Availability validation failed")
        cleaned_data['in_stock'] = cleaned_availability
        
        # Validate product title
        title_valid, cleaned_title = self._validate_product_title(data.get('product_title'))
        if not title_valid:
            validation_errors.append("Product title validation failed")
        cleaned_data['product_title'] = cleaned_title
        
        # Validate response time
        response_time_valid, cleaned_response_time = self._validate_response_time(
            data.get('response_time')
        )
        if not response_time_valid:
            validation_errors.append("Response time validation failed")
        cleaned_data['response_time'] = cleaned_response_time
        
        # Add validation metadata
        cleaned_data['validation_errors'] = validation_errors
        cleaned_data['validation_passed'] = len(validation_errors) == 0
        cleaned_data['validated_at'] = datetime.now().isoformat()
        
        return len(validation_errors) == 0, cleaned_data
        
    def _validate_price(self, price: Any) -> Tuple[bool, Optional[float], Optional[str]]:
        """Validate price value."""
        if price is None:
            return False, None, "Price is None"
            
        try:
            # Convert to float if string
            if isinstance(price, str):
                # Clean price string
                cleaned_price_str = re.sub(r'[^\d.]', '', price)
                if not cleaned_price_str:
                    return False, None, "No numeric value found in price string"
                price = float(cleaned_price_str)
            elif not isinstance(price, (int, float)):
                return False, None, f"Invalid price type: {type(price)}"
                
            price = float(price)
            
            # Check price range
            if price < self.min_price:
                return False, None, f"Price {price} below minimum {self.min_price}"
            if price > self.max_price:
                return False, None, f"Price {price} above maximum {self.max_price}"
                
            # Round to 2 decimal places
            price = round(price, 2)
            
            return True, price, None
            
        except (ValueError, TypeError) as e:
            return False, None, f"Price conversion error: {str(e)}"
            
    def _validate_availability(self, in_stock: Any, availability_text: str) -> Tuple[bool, Optional[bool]]:
        """Validate availability data."""
        if in_stock is None:
            # Try to infer from availability text
            if availability_text:
                availability_lower = availability_text.lower()
                if any(indicator in availability_lower for indicator in [
                    'out of stock', 'unavailable', 'not available', 'sold out'
                ]):
                    return True, False
                elif any(indicator in availability_lower for indicator in [
                    'in stock', 'available', 'add to basket', 'add to trolley'
                ]):
                    return True, True
            return False, None
            
        if isinstance(in_stock, bool):
            return True, in_stock
        elif isinstance(in_stock, str):
            in_stock_lower = in_stock.lower()
            if in_stock_lower in ['true', '1', 'yes', 'available', 'in stock']:
                return True, True
            elif in_stock_lower in ['false', '0', 'no', 'unavailable', 'out of stock']:
                return True, False
                
        return False, None
        
    def _validate_product_title(self, title: Any) -> Tuple[bool, Optional[str]]:
        """Validate product title."""
        if title is None:
            return False, None
            
        if not isinstance(title, str):
            title = str(title)
            
        # Clean title
        title = title.strip()
        
        # Check minimum length
        if len(title) < 3:
            return False, None
            
        # Check maximum length
        if len(title) > 500:
            title = title[:500]
            
        return True, title
        
    def _validate_response_time(self, response_time: Any) -> Tuple[bool, Optional[float]]:
        """Validate response time."""
        if response_time is None:
            return False, None
            
        try:
            response_time = float(response_time)
            
            # Check reasonable bounds (0.1 seconds to 5 minutes)
            if response_time < 0.1 or response_time > 300:
                return False, None
                
            return True, round(response_time, 3)
            
        except (ValueError, TypeError):
            return False, None


class DataQualityChecker:
    """Checks data quality and identifies anomalies."""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    def check_price_anomalies(self, sku_id: int, retailer_id: int, 
                             new_price: float, days_back: int = 7) -> Dict[str, Any]:
        """Check for price anomalies compared to historical data."""
        anomalies = {
            'has_anomaly': False,
            'anomaly_type': None,
            'anomaly_details': {},
            'historical_stats': {}
        }
        
        try:
            # Get historical prices
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT price, scraped_at 
                    FROM price_history 
                    WHERE sku_id = ? AND retailer_id = ? 
                    AND scraped_at >= datetime('now', '-{} days')
                    AND price IS NOT NULL
                    ORDER BY scraped_at DESC
                """.format(days_back), (sku_id, retailer_id))
                
                historical_prices = [row[0] for row in cursor.fetchall()]
                
            if len(historical_prices) < 2:
                return anomalies  # Not enough data for comparison
                
            # Calculate statistics
            avg_price = sum(historical_prices) / len(historical_prices)
            min_price = min(historical_prices)
            max_price = max(historical_prices)
            
            anomalies['historical_stats'] = {
                'count': len(historical_prices),
                'average': round(avg_price, 2),
                'min': min_price,
                'max': max_price,
                'range': round(max_price - min_price, 2)
            }
            
            # Check for significant price changes
            price_change_threshold = 0.2  # 20% change threshold
            
            if new_price > avg_price * (1 + price_change_threshold):
                anomalies['has_anomaly'] = True
                anomalies['anomaly_type'] = 'price_spike'
                anomalies['anomaly_details'] = {
                    'new_price': new_price,
                    'average_price': round(avg_price, 2),
                    'increase_percentage': round(((new_price - avg_price) / avg_price) * 100, 1)
                }
            elif new_price < avg_price * (1 - price_change_threshold):
                anomalies['has_anomaly'] = True
                anomalies['anomaly_type'] = 'price_drop'
                anomalies['anomaly_details'] = {
                    'new_price': new_price,
                    'average_price': round(avg_price, 2),
                    'decrease_percentage': round(((avg_price - new_price) / avg_price) * 100, 1)
                }
                
        except Exception as e:
            logger.error(f"Error checking price anomalies: {str(e)}")
            
        return anomalies
        
    def check_data_freshness(self, max_age_hours: int = 48) -> Dict[str, Any]:
        """Check data freshness across all SKUs and retailers."""
        freshness_report = {
            'stale_data_count': 0,
            'total_sku_retailer_pairs': 0,
            'stale_pairs': [],
            'freshness_percentage': 0
        }
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all active SKU-retailer pairs
                cursor.execute("""
                    SELECT sru.sku_id, sru.retailer_id, sc.brand, sc.product_name, rc.name
                    FROM sku_retailer_urls sru
                    JOIN sku_config sc ON sru.sku_id = sc.id
                    JOIN retailer_config rc ON sru.retailer_id = rc.id
                    WHERE sru.active = 1 AND sc.active = 1 AND rc.active = 1
                """)
                
                all_pairs = cursor.fetchall()
                freshness_report['total_sku_retailer_pairs'] = len(all_pairs)
                
                # Check each pair for recent data
                for sku_id, retailer_id, brand, product_name, retailer_name in all_pairs:
                    cursor.execute("""
                        SELECT MAX(scraped_at) as last_scraped
                        FROM price_history
                        WHERE sku_id = ? AND retailer_id = ?
                    """, (sku_id, retailer_id))
                    
                    result = cursor.fetchone()
                    last_scraped = result[0] if result and result[0] else None
                    
                    if not last_scraped or datetime.fromisoformat(last_scraped.replace('Z', '+00:00').replace('+00:00', '')) < cutoff_time:
                        freshness_report['stale_data_count'] += 1
                        freshness_report['stale_pairs'].append({
                            'sku_id': sku_id,
                            'retailer_id': retailer_id,
                            'brand': brand,
                            'product_name': product_name,
                            'retailer_name': retailer_name,
                            'last_scraped': last_scraped
                        })
                        
                # Calculate freshness percentage
                if freshness_report['total_sku_retailer_pairs'] > 0:
                    fresh_count = freshness_report['total_sku_retailer_pairs'] - freshness_report['stale_data_count']
                    freshness_report['freshness_percentage'] = round(
                        (fresh_count / freshness_report['total_sku_retailer_pairs']) * 100, 1
                    )
                    
        except Exception as e:
            logger.error(f"Error checking data freshness: {str(e)}")
            
        return freshness_report
        
    def generate_quality_report(self) -> Dict[str, Any]:
        """Generate comprehensive data quality report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'freshness': self.check_data_freshness(),
            'summary': {}
        }
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get scrape success rate for last 24 hours
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_attempts,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_attempts
                    FROM scrape_logs 
                    WHERE scraped_at >= datetime('now', '-1 day')
                """)
                
                scrape_stats = cursor.fetchone()
                if scrape_stats and scrape_stats[0] > 0:
                    success_rate = (scrape_stats[1] / scrape_stats[0]) * 100
                    report['summary']['scrape_success_rate'] = round(success_rate, 1)
                    report['summary']['total_scrape_attempts_24h'] = scrape_stats[0]
                    report['summary']['successful_scrapes_24h'] = scrape_stats[1]
                else:
                    report['summary']['scrape_success_rate'] = 0
                    report['summary']['total_scrape_attempts_24h'] = 0
                    report['summary']['successful_scrapes_24h'] = 0
                    
                # Get price data count for last 24 hours
                cursor.execute("""
                    SELECT COUNT(*) as price_records
                    FROM price_history 
                    WHERE scraped_at >= datetime('now', '-1 day')
                    AND price IS NOT NULL
                """)
                
                price_count = cursor.fetchone()
                report['summary']['price_records_24h'] = price_count[0] if price_count else 0
                
        except Exception as e:
            logger.error(f"Error generating quality report: {str(e)}")
            
        return report