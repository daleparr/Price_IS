"""
Daily scheduling and automation system for the price tracker.
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import threading

from src.main import PriceTrackerOrchestrator

logger = logging.getLogger(__name__)


class PriceTrackerScheduler:
    """Scheduler for automated price tracking operations."""
    
    def __init__(self, config_path: str = "config/settings.ini"):
        self.orchestrator = PriceTrackerOrchestrator(config_path)
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.last_scrape_time: Optional[datetime] = None
        self.last_health_check_time: Optional[datetime] = None
        
    def schedule_daily_scrape(self, time_str: str = "09:00"):
        """Schedule daily scraping at specified time."""
        schedule.every().day.at(time_str).do(self._run_daily_scrape)
        logger.info(f"Scheduled daily scrape at {time_str}")
        
    def schedule_health_checks(self, interval_hours: int = 6):
        """Schedule periodic health checks."""
        schedule.every(interval_hours).hours.do(self._run_health_check)
        logger.info(f"Scheduled health checks every {interval_hours} hours")
        
    def schedule_data_quality_checks(self, interval_hours: int = 12):
        """Schedule periodic data quality checks."""
        schedule.every(interval_hours).hours.do(self._run_data_quality_check)
        logger.info(f"Scheduled data quality checks every {interval_hours} hours")
        
    def _run_daily_scrape(self):
        """Run daily scrape in async context."""
        logger.info("Starting scheduled daily scrape")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            summary = loop.run_until_complete(self.orchestrator.run_full_scrape())
            self.last_scrape_time = datetime.now()
            
            logger.info(f"Daily scrape completed: {summary}")
            
            # Send notifications if configured
            self._send_scrape_notification(summary)
            
        except Exception as e:
            logger.error(f"Error in scheduled daily scrape: {str(e)}")
        finally:
            loop.close()
            
    def _run_health_check(self):
        """Run health check in async context."""
        logger.info("Starting scheduled health check")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            health_status = loop.run_until_complete(self.orchestrator.run_health_check())
            self.last_health_check_time = datetime.now()
            
            # Send alerts if system is unhealthy
            if health_status.get('overall_status') != 'healthy':
                self._send_health_alert(health_status)
                
        except Exception as e:
            logger.error(f"Error in scheduled health check: {str(e)}")
        finally:
            loop.close()
            
    def _run_data_quality_check(self):
        """Run data quality check."""
        logger.info("Starting scheduled data quality check")
        try:
            quality_report = self.orchestrator.run_data_quality_check()
            
            # Check for quality issues
            freshness = quality_report.get('freshness', {})
            if freshness.get('stale_percentage', 0) > 30:
                logger.warning(f"High stale data percentage: {freshness['stale_percentage']}%")
                
        except Exception as e:
            logger.error(f"Error in scheduled data quality check: {str(e)}")
            
    def _send_scrape_notification(self, summary: Dict[str, Any]):
        """Send notification about scrape results."""
        # This would integrate with email/Slack if configured
        success_rate = summary.get('success_rate', 0)
        
        if success_rate < 80:
            logger.warning(f"Low scrape success rate: {success_rate}%")
            # TODO: Implement email/Slack notifications
            
    def _send_health_alert(self, health_status: Dict[str, Any]):
        """Send alert about system health issues."""
        # This would integrate with email/Slack if configured
        status = health_status.get('overall_status', 'unknown')
        issues = health_status.get('issues', [])
        
        logger.error(f"System health alert - Status: {status}, Issues: {issues}")
        # TODO: Implement email/Slack alerts
        
    def start_scheduler(self):
        """Start the scheduler in a background thread."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
            
        self.is_running = True
        
        # Set up default schedules
        self.schedule_daily_scrape("09:00")  # 9 AM daily scrape
        self.schedule_health_checks(6)       # Health check every 6 hours
        self.schedule_data_quality_checks(12) # Quality check every 12 hours
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Price tracker scheduler started")
        
    def _run_scheduler(self):
        """Run the scheduler loop."""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)
                
    def stop_scheduler(self):
        """Stop the scheduler."""
        self.is_running = False
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        logger.info("Price tracker scheduler stopped")
        
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        return {
            'is_running': self.is_running,
            'last_scrape_time': self.last_scrape_time.isoformat() if self.last_scrape_time else None,
            'last_health_check_time': self.last_health_check_time.isoformat() if self.last_health_check_time else None,
            'scheduled_jobs': len(schedule.jobs),
            'next_run_times': [
                {
                    'job': str(job.job_func.__name__),
                    'next_run': job.next_run.isoformat() if job.next_run else None
                }
                for job in schedule.jobs
            ]
        }
        
    def run_manual_scrape(self) -> Dict[str, Any]:
        """Run a manual scrape immediately."""
        logger.info("Running manual scrape")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            summary = loop.run_until_complete(self.orchestrator.run_full_scrape())
            self.last_scrape_time = datetime.now()
            
            return summary
            
        except Exception as e:
            logger.error(f"Error in manual scrape: {str(e)}")
            raise
        finally:
            loop.close()


def main():
    """Main entry point for scheduler."""
    import signal
    import sys
    
    scheduler = PriceTrackerScheduler()
    
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        scheduler.stop_scheduler()
        sys.exit(0)
        
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize database
        scheduler.orchestrator.db_manager.create_tables()
        
        # Start scheduler
        scheduler.start_scheduler()
        
        logger.info("Price tracker scheduler is running. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        scheduler.stop_scheduler()


if __name__ == "__main__":
    main()