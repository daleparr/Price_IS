"""
Health monitoring and logging system for the price tracker.
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors system health and performance metrics."""
    
    def __init__(self, db_manager, settings: Dict[str, Any]):
        self.db_manager = db_manager
        self.settings = settings
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration."""
        log_level = self.settings.get('log_level', 'INFO')
        log_file = self.settings.get('log_file', 'logs/price_tracker.log')
        
        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
    def log_scrape_attempt(self, sku_id: int, retailer_id: int, status: str,
                          error_message: str = None, response_time: float = None,
                          user_agent: str = None, additional_data: Dict[str, Any] = None):
        """Log a scrape attempt with detailed information."""
        try:
            # Store in database
            log_id = self.db_manager.log_scrape_attempt(
                sku_id=sku_id,
                retailer_id=retailer_id,
                status=status,
                error_message=error_message,
                response_time=response_time,
                user_agent=user_agent
            )
            
            # Log to file
            log_data = {
                'log_id': log_id,
                'sku_id': sku_id,
                'retailer_id': retailer_id,
                'status': status,
                'response_time': response_time,
                'timestamp': datetime.now().isoformat()
            }
            
            if error_message:
                log_data['error'] = error_message
                
            if additional_data:
                log_data.update(additional_data)
                
            if status == 'success':
                logger.info(f"Scrape successful: {json.dumps(log_data)}")
            elif status == 'failed':
                logger.error(f"Scrape failed: {json.dumps(log_data)}")
            else:
                logger.warning(f"Scrape partial: {json.dumps(log_data)}")
                
        except Exception as e:
            logger.error(f"Error logging scrape attempt: {str(e)}")
            
    def record_health_metric(self, metric_name: str, metric_value: float = None, 
                           metric_text: str = None):
        """Record a health metric."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO health_metrics (metric_name, metric_value, metric_text)
                    VALUES (?, ?, ?)
                """, (metric_name, metric_value, metric_text))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error recording health metric: {str(e)}")
            
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'issues': [],
            'metrics': {}
        }
        
        try:
            # Check scrape success rate
            scrape_health = self._check_scrape_health()
            health_status['metrics']['scrape_health'] = scrape_health
            
            if scrape_health['success_rate'] < 80:
                health_status['overall_status'] = 'degraded'
                health_status['issues'].append(f"Low scrape success rate: {scrape_health['success_rate']}%")
                
            # Check data freshness
            freshness_health = self._check_data_freshness()
            health_status['metrics']['data_freshness'] = freshness_health
            
            if freshness_health['stale_percentage'] > 20:
                health_status['overall_status'] = 'degraded'
                health_status['issues'].append(f"High stale data percentage: {freshness_health['stale_percentage']}%")
                
            # Check error rates
            error_health = self._check_error_rates()
            health_status['metrics']['error_rates'] = error_health
            
            if error_health['error_rate'] > 30:
                health_status['overall_status'] = 'unhealthy'
                health_status['issues'].append(f"High error rate: {error_health['error_rate']}%")
                
            # Check database health
            db_health = self._check_database_health()
            health_status['metrics']['database'] = db_health
            
            if not db_health['accessible']:
                health_status['overall_status'] = 'unhealthy'
                health_status['issues'].append("Database not accessible")
                
            # Record overall health metric
            self.record_health_metric(
                'overall_health_status',
                metric_text=health_status['overall_status']
            )
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            health_status['overall_status'] = 'unhealthy'
            health_status['issues'].append(f"Health check error: {str(e)}")
            
        return health_status
        
    def _check_scrape_health(self) -> Dict[str, Any]:
        """Check scraping system health."""
        health = {
            'success_rate': 0,
            'total_attempts': 0,
            'successful_attempts': 0,
            'failed_attempts': 0,
            'average_response_time': 0
        }
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get scrape stats for last 24 hours
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                        AVG(response_time) as avg_response_time
                    FROM scrape_logs 
                    WHERE scraped_at >= datetime('now', '-1 day')
                """)
                
                result = cursor.fetchone()
                if result and result[0] > 0:
                    health['total_attempts'] = result[0]
                    health['successful_attempts'] = result[1] or 0
                    health['failed_attempts'] = result[2] or 0
                    health['success_rate'] = round((health['successful_attempts'] / health['total_attempts']) * 100, 1)
                    health['average_response_time'] = round(result[3] or 0, 2)
                    
        except Exception as e:
            logger.error(f"Error checking scrape health: {str(e)}")
            
        return health
        
    def _check_data_freshness(self) -> Dict[str, Any]:
        """Check data freshness."""
        freshness = {
            'total_sku_retailer_pairs': 0,
            'fresh_data_count': 0,
            'stale_data_count': 0,
            'stale_percentage': 0,
            'oldest_data_age_hours': 0
        }
        
        try:
            max_age_hours = self.settings.get('stale_data_hours', 48)
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all active SKU-retailer pairs
                cursor.execute("""
                    SELECT COUNT(*) FROM sku_retailer_urls sru
                    JOIN sku_config sc ON sru.sku_id = sc.id
                    JOIN retailer_config rc ON sru.retailer_id = rc.id
                    WHERE sru.active = 1 AND sc.active = 1 AND rc.active = 1
                """)
                
                total_pairs = cursor.fetchone()[0]
                freshness['total_sku_retailer_pairs'] = total_pairs
                
                # Count fresh data
                cursor.execute("""
                    SELECT COUNT(DISTINCT sku_id || '-' || retailer_id)
                    FROM price_history
                    WHERE scraped_at >= datetime('now', '-{} hours')
                """.format(max_age_hours))
                
                fresh_count = cursor.fetchone()[0]
                freshness['fresh_data_count'] = fresh_count
                freshness['stale_data_count'] = total_pairs - fresh_count
                
                if total_pairs > 0:
                    freshness['stale_percentage'] = round((freshness['stale_data_count'] / total_pairs) * 100, 1)
                    
                # Get oldest data age
                cursor.execute("""
                    SELECT MIN(scraped_at) FROM price_history
                """)
                
                oldest_data = cursor.fetchone()[0]
                if oldest_data:
                    oldest_datetime = datetime.fromisoformat(oldest_data.replace('Z', '+00:00').replace('+00:00', ''))
                    age_hours = (datetime.now() - oldest_datetime).total_seconds() / 3600
                    freshness['oldest_data_age_hours'] = round(age_hours, 1)
                    
        except Exception as e:
            logger.error(f"Error checking data freshness: {str(e)}")
            
        return freshness
        
    def _check_error_rates(self) -> Dict[str, Any]:
        """Check error rates by retailer."""
        error_rates = {
            'overall_error_rate': 0,
            'error_rate': 0,
            'retailer_error_rates': []
        }
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Overall error rate for last 24 hours
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM scrape_logs 
                    WHERE scraped_at >= datetime('now', '-1 day')
                """)
                
                result = cursor.fetchone()
                if result and result[0] > 0:
                    error_rates['error_rate'] = round((result[1] / result[0]) * 100, 1)
                    
                # Error rates by retailer
                cursor.execute("""
                    SELECT 
                        rc.name,
                        COUNT(*) as total,
                        SUM(CASE WHEN sl.status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM scrape_logs sl
                    JOIN retailer_config rc ON sl.retailer_id = rc.id
                    WHERE sl.scraped_at >= datetime('now', '-1 day')
                    GROUP BY rc.name
                    HAVING COUNT(*) > 0
                """)
                
                for retailer_name, total, failed in cursor.fetchall():
                    retailer_error_rate = round((failed / total) * 100, 1) if total > 0 else 0
                    error_rates['retailer_error_rates'].append({
                        'retailer': retailer_name,
                        'error_rate': retailer_error_rate,
                        'total_attempts': total,
                        'failed_attempts': failed
                    })
                    
        except Exception as e:
            logger.error(f"Error checking error rates: {str(e)}")
            
        return error_rates
        
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database health."""
        db_health = {
            'accessible': False,
            'total_records': 0,
            'recent_records': 0,
            'database_size_mb': 0
        }
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if database is accessible
                cursor.execute("SELECT 1")
                db_health['accessible'] = True
                
                # Get total price records
                cursor.execute("SELECT COUNT(*) FROM price_history")
                db_health['total_records'] = cursor.fetchone()[0]
                
                # Get recent records (last 24 hours)
                cursor.execute("""
                    SELECT COUNT(*) FROM price_history 
                    WHERE scraped_at >= datetime('now', '-1 day')
                """)
                db_health['recent_records'] = cursor.fetchone()[0]
                
                # Get database file size
                try:
                    db_path = Path(self.db_manager.db_path)
                    if db_path.exists():
                        size_bytes = db_path.stat().st_size
                        db_health['database_size_mb'] = round(size_bytes / (1024 * 1024), 2)
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error(f"Error checking database health: {str(e)}")
            db_health['accessible'] = False
            
        return db_health
        
    def generate_health_report(self) -> str:
        """Generate a human-readable health report."""
        health = self.get_system_health()
        
        report_lines = [
            f"=== Price Tracker Health Report ===",
            f"Generated: {health['timestamp']}",
            f"Overall Status: {health['overall_status'].upper()}",
            ""
        ]
        
        if health['issues']:
            report_lines.append("Issues:")
            for issue in health['issues']:
                report_lines.append(f"  - {issue}")
            report_lines.append("")
            
        # Scrape health
        scrape_health = health['metrics'].get('scrape_health', {})
        report_lines.extend([
            "Scraping Health:",
            f"  Success Rate: {scrape_health.get('success_rate', 0)}%",
            f"  Total Attempts (24h): {scrape_health.get('total_attempts', 0)}",
            f"  Average Response Time: {scrape_health.get('average_response_time', 0)}s",
            ""
        ])
        
        # Data freshness
        freshness = health['metrics'].get('data_freshness', {})
        report_lines.extend([
            "Data Freshness:",
            f"  Fresh Data: {freshness.get('fresh_data_count', 0)}/{freshness.get('total_sku_retailer_pairs', 0)}",
            f"  Stale Percentage: {freshness.get('stale_percentage', 0)}%",
            ""
        ])
        
        # Database health
        db_health = health['metrics'].get('database', {})
        report_lines.extend([
            "Database Health:",
            f"  Accessible: {'Yes' if db_health.get('accessible') else 'No'}",
            f"  Total Records: {db_health.get('total_records', 0)}",
            f"  Recent Records (24h): {db_health.get('recent_records', 0)}",
            f"  Database Size: {db_health.get('database_size_mb', 0)} MB",
        ])
        
        return "\n".join(report_lines)