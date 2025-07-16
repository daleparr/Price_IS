"""
Main orchestrator for the price tracker system.
"""

import asyncio
import configparser
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from src.database.models import DatabaseManager
from src.scrapers.scraper_factory import ScraperFactory
from src.utils.data_validator import PriceValidator, DataQualityChecker
from src.utils.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)


class PriceTrackerOrchestrator:
    """Main orchestrator for price tracking operations."""
    
    def __init__(self, config_path: str = "config/settings.ini"):
        self.config_path = config_path
        self.settings = self._load_settings()
        self.db_manager = DatabaseManager(self.settings['database']['db_path'])
        self.health_monitor = HealthMonitor(self.db_manager, self.settings['logging'])
        self.price_validator = PriceValidator(self.settings['scraping'])
        self.quality_checker = DataQualityChecker(self.db_manager)
        
    def _load_settings(self) -> Dict[str, Dict[str, Any]]:
        """Load configuration settings."""
        config = configparser.ConfigParser()
        config.read(self.config_path)
        
        settings = {}
        for section in config.sections():
            settings[section] = dict(config[section])
            
        # Convert numeric values
        for section, values in settings.items():
            for key, value in values.items():
                try:
                    # Try to convert to int
                    if value.isdigit():
                        settings[section][key] = int(value)
                    # Try to convert to float
                    elif '.' in value and value.replace('.', '').isdigit():
                        settings[section][key] = float(value)
                    # Convert boolean strings
                    elif value.lower() in ['true', 'false']:
                        settings[section][key] = value.lower() == 'true'
                except (ValueError, AttributeError):
                    pass
                    
        return settings
        
    def _load_retailer_configs(self) -> List[Dict[str, Any]]:
        """Load retailer configurations."""
        with open("config/retailers.json", "r") as f:
            data = json.load(f)
        return [retailer for retailer in data["retailers"] if retailer["active"]]
        
    def _load_sku_configs(self) -> List[Dict[str, Any]]:
        """Load SKU configurations."""
        with open("config/skus.json", "r") as f:
            data = json.load(f)
        return [sku for sku in data["skus"] if sku["active"]]
        
    async def scrape_single_product(self, sku_data: Dict[str, Any], 
                                   retailer_config: Dict[str, Any], 
                                   product_url: str) -> Dict[str, Any]:
        """Scrape a single product and store the result."""
        scrape_result = {
            'sku_id': sku_data['id'],
            'retailer_id': retailer_config['id'],
            'success': False,
            'error': None,
            'price_data': None
        }
        
        try:
            # Create scraper instance
            scraper = ScraperFactory.create_scraper(retailer_config, self.settings['scraping'])
            
            # Perform scraping
            async with scraper:
                result = await scraper.scrape_product(product_url, sku_data)
                
            # Validate scraped data
            is_valid, cleaned_data = self.price_validator.validate_price_data(result)
            
            if is_valid and cleaned_data['success']:
                # Store price data
                price_id = self.db_manager.insert_price_data(
                    sku_id=sku_data['id'],
                    retailer_id=retailer_config['id'],
                    price=cleaned_data['price'],
                    in_stock=cleaned_data['in_stock'],
                    availability_text=cleaned_data.get('availability_text'),
                    product_title=cleaned_data.get('product_title'),
                    raw_data=json.dumps(cleaned_data.get('raw_data', {}))
                )
                
                # Check for price anomalies
                anomalies = self.quality_checker.check_price_anomalies(
                    sku_id=sku_data['id'],
                    retailer_id=retailer_config['id'],
                    new_price=cleaned_data['price']
                )
                
                # Log successful scrape
                self.health_monitor.log_scrape_attempt(
                    sku_id=sku_data['id'],
                    retailer_id=retailer_config['id'],
                    status='success',
                    response_time=cleaned_data.get('response_time'),
                    additional_data={
                        'price_id': price_id,
                        'price': cleaned_data['price'],
                        'anomalies': anomalies
                    }
                )
                
                scrape_result['success'] = True
                scrape_result['price_data'] = cleaned_data
                
                logger.info(f"Successfully scraped {sku_data['brand']} {sku_data['product_name']} "
                           f"from {retailer_config['name']}: £{cleaned_data['price']}")
                
            else:
                # Log validation failure
                error_msg = f"Data validation failed: {cleaned_data.get('validation_errors', [])}"
                self.health_monitor.log_scrape_attempt(
                    sku_id=sku_data['id'],
                    retailer_id=retailer_config['id'],
                    status='failed',
                    error_message=error_msg,
                    response_time=result.get('response_time')
                )
                
                scrape_result['error'] = error_msg
                
        except Exception as e:
            error_msg = f"Scraping error: {str(e)}"
            logger.error(f"Error scraping {sku_data['brand']} from {retailer_config['name']}: {error_msg}")
            
            # Log failed scrape
            self.health_monitor.log_scrape_attempt(
                sku_id=sku_data['id'],
                retailer_id=retailer_config['id'],
                status='failed',
                error_message=error_msg
            )
            
            scrape_result['error'] = error_msg
            
        return scrape_result
        
    async def run_full_scrape(self) -> Dict[str, Any]:
        """Run a full scraping cycle for all configured SKUs and retailers."""
        start_time = time.time()
        logger.info("Starting full scrape cycle")
        
        # Get configurations
        sku_configs = self._load_sku_configs()
        retailer_configs = self._load_retailer_configs()
        
        # Get URL mappings from database
        url_mappings = self.db_manager.get_sku_retailer_urls()
        
        # Create mapping lookup
        url_lookup = {}
        for mapping in url_mappings:
            key = f"{mapping['sku_id']}-{mapping['retailer_id']}"
            url_lookup[key] = mapping['product_url']
            
        # Prepare scraping tasks
        scrape_tasks = []
        for sku in sku_configs:
            for retailer in retailer_configs:
                key = f"{sku['id']}-{retailer['id']}"
                if key in url_lookup:
                    scrape_tasks.append({
                        'sku': sku,
                        'retailer': retailer,
                        'url': url_lookup[key]
                    })
                    
        logger.info(f"Prepared {len(scrape_tasks)} scraping tasks")
        
        # Execute scraping with concurrency control
        max_concurrent = self.settings['scraping'].get('concurrent_scrapers', 3)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(task):
            async with semaphore:
                return await self.scrape_single_product(
                    task['sku'], 
                    task['retailer'], 
                    task['url']
                )
                
        # Run all scraping tasks
        results = await asyncio.gather(
            *[scrape_with_semaphore(task) for task in scrape_tasks],
            return_exceptions=True
        )
        
        # Analyze results
        successful_scrapes = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
        failed_scrapes = len(results) - successful_scrapes
        
        total_time = time.time() - start_time
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_tasks': len(scrape_tasks),
            'successful_scrapes': successful_scrapes,
            'failed_scrapes': failed_scrapes,
            'success_rate': round((successful_scrapes / len(results)) * 100, 1) if results else 0,
            'total_time_seconds': round(total_time, 2),
            'average_time_per_scrape': round(total_time / len(results), 2) if results else 0
        }
        
        logger.info(f"Scrape cycle completed: {summary}")
        
        # Record health metrics
        self.health_monitor.record_health_metric(
            'scrape_cycle_success_rate',
            summary['success_rate']
        )
        self.health_monitor.record_health_metric(
            'scrape_cycle_duration',
            summary['total_time_seconds']
        )
        
        return summary
        
    async def run_health_check(self) -> Dict[str, Any]:
        """Run system health check."""
        logger.info("Running health check")
        health_status = self.health_monitor.get_system_health()
        
        # Generate and log health report
        health_report = self.health_monitor.generate_health_report()
        logger.info(f"Health Report:\n{health_report}")
        
        return health_status
        
    def run_data_quality_check(self) -> Dict[str, Any]:
        """Run data quality check."""
        logger.info("Running data quality check")
        quality_report = self.quality_checker.generate_quality_report()
        
        logger.info(f"Data Quality Report: {json.dumps(quality_report, indent=2)}")
        return quality_report


async def main():
    """Main entry point."""
    orchestrator = PriceTrackerOrchestrator()
    
    # Initialize database if needed
    orchestrator.db_manager.create_tables()
    
    # Run health check
    await orchestrator.run_health_check()
    
    # Run full scrape
    scrape_summary = await orchestrator.run_full_scrape()
    
    # Run data quality check
    quality_report = orchestrator.run_data_quality_check()
    
    print("\n=== Scrape Summary ===")
    print(json.dumps(scrape_summary, indent=2))
    
    print("\n=== Quality Report ===")
    print(json.dumps(quality_report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())