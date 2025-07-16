"""
Database models and schema definitions for the price tracker system.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for the price tracker."""
    
    def __init__(self, db_path: str = None):
        # Use absolute path for Streamlit Cloud compatibility
        if db_path is None:
            # Get the absolute path to the project root
            project_root = Path(__file__).parent.parent.parent
            self.db_path = str(project_root / "data" / "price_tracker.db")
        else:
            self.db_path = db_path
        self.ensure_data_directory()
        
    def ensure_data_directory(self):
        """Ensure the data directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def create_tables(self):
        """Create all database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # SKU Configuration Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sku_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    brand TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    pack_size TEXT NOT NULL,
                    formulation TEXT,
                    category TEXT,
                    active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Retailer Configuration Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS retailer_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    base_url TEXT NOT NULL,
                    scraper_module TEXT NOT NULL,
                    selectors TEXT, -- JSON string
                    wait_selectors TEXT, -- JSON string
                    active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # SKU-Retailer URL Mapping Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sku_retailer_urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_id INTEGER NOT NULL,
                    retailer_id INTEGER NOT NULL,
                    product_url TEXT NOT NULL,
                    custom_selectors TEXT, -- JSON string for retailer-specific overrides
                    active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sku_id) REFERENCES sku_config (id),
                    FOREIGN KEY (retailer_id) REFERENCES retailer_config (id),
                    UNIQUE(sku_id, retailer_id)
                )
            """)
            
            # Price History Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_id INTEGER NOT NULL,
                    retailer_id INTEGER NOT NULL,
                    price DECIMAL(10,2),
                    currency TEXT DEFAULT 'GBP',
                    in_stock BOOLEAN,
                    availability_text TEXT,
                    product_title TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_data TEXT, -- JSON string of all scraped data
                    FOREIGN KEY (sku_id) REFERENCES sku_config (id),
                    FOREIGN KEY (retailer_id) REFERENCES retailer_config (id)
                )
            """)
            
            # Scrape Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_id INTEGER,
                    retailer_id INTEGER,
                    status TEXT NOT NULL, -- 'success', 'failed', 'partial'
                    error_message TEXT,
                    response_time REAL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_agent TEXT,
                    ip_address TEXT,
                    FOREIGN KEY (sku_id) REFERENCES sku_config (id),
                    FOREIGN KEY (retailer_id) REFERENCES retailer_config (id)
                )
            """)
            
            # Health Metrics Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    metric_text TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Scheduling Configuration Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_enabled BOOLEAN DEFAULT 0,
                    schedule_time TEXT, -- Time in HH:MM format
                    schedule_timezone TEXT DEFAULT 'UTC',
                    last_run TIMESTAMP,
                    next_run TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_sku_retailer ON price_history(sku_id, retailer_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_scraped_at ON price_history(scraped_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrape_logs_status ON scrape_logs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrape_logs_scraped_at ON scrape_logs(scraped_at)")
            
            conn.commit()
            logger.info("Database tables created successfully")
            
    def insert_sku(self, brand: str, product_name: str, pack_size: str, 
                   formulation: str = None, category: str = None) -> int:
        """Insert a new SKU configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sku_config (brand, product_name, pack_size, formulation, category)
                VALUES (?, ?, ?, ?, ?)
            """, (brand, product_name, pack_size, formulation, category))
            return cursor.lastrowid
            
    def insert_retailer(self, name: str, base_url: str, scraper_module: str,
                       selectors: str = None, wait_selectors: str = None) -> int:
        """Insert a new retailer configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO retailer_config (name, base_url, scraper_module, selectors, wait_selectors)
                VALUES (?, ?, ?, ?, ?)
            """, (name, base_url, scraper_module, selectors, wait_selectors))
            return cursor.lastrowid
            
    def insert_price_data(self, sku_id: int, retailer_id: int, price: float,
                         in_stock: bool, availability_text: str = None,
                         product_title: str = None, raw_data: str = None) -> int:
        """Insert price data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_history (sku_id, retailer_id, price, in_stock, 
                                         availability_text, product_title, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sku_id, retailer_id, price, in_stock, availability_text, product_title, raw_data))
            return cursor.lastrowid
            
    def log_scrape_attempt(self, sku_id: int, retailer_id: int, status: str,
                          error_message: str = None, response_time: float = None,
                          user_agent: str = None) -> int:
        """Log a scrape attempt."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scrape_logs (sku_id, retailer_id, status, error_message, 
                                       response_time, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sku_id, retailer_id, status, error_message, response_time, user_agent))
            return cursor.lastrowid
    
    def get_scrape_logs(self, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent scrape logs with SKU and retailer details."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sl.*, sc.brand, sc.product_name, rc.name as retailer_name
                FROM scrape_logs sl
                LEFT JOIN sku_config sc ON sl.sku_id = sc.id
                LEFT JOIN retailer_config rc ON sl.retailer_id = rc.id
                WHERE sl.scraped_at >= datetime('now', '-{} days')
                ORDER BY sl.scraped_at DESC
                LIMIT ?
            """.format(days), (limit,))
            return [dict(row) for row in cursor.fetchall()]
            
    def get_active_skus(self) -> List[Dict[str, Any]]:
        """Get all active SKUs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sku_config WHERE active = 1")
            return [dict(row) for row in cursor.fetchall()]
            
    def get_active_retailers(self) -> List[Dict[str, Any]]:
        """Get all active retailers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM retailer_config WHERE active = 1")
            return [dict(row) for row in cursor.fetchall()]
            
    def get_sku_retailer_urls(self) -> List[Dict[str, Any]]:
        """Get all active SKU-retailer URL mappings."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sru.*, sc.brand, sc.product_name, sc.pack_size,
                       rc.name as retailer_name, rc.base_url, rc.selectors
                FROM sku_retailer_urls sru
                JOIN sku_config sc ON sru.sku_id = sc.id
                JOIN retailer_config rc ON sru.retailer_id = rc.id
                WHERE sru.active = 1 AND sc.active = 1 AND rc.active = 1
            """)
            return [dict(row) for row in cursor.fetchall()]
            
    def get_latest_prices(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get latest prices for all SKUs within specified days."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ph.*, sc.brand, sc.product_name, sc.pack_size,
                       rc.name as retailer_name
                FROM price_history ph
                JOIN sku_config sc ON ph.sku_id = sc.id
                JOIN retailer_config rc ON ph.retailer_id = rc.id
                WHERE ph.scraped_at >= datetime('now', '-{} days')
                ORDER BY ph.scraped_at DESC
            """.format(days))
            return [dict(row) for row in cursor.fetchall()]
            
    def get_health_summary(self) -> Dict[str, Any]:
        """Get system health summary."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get scrape success rate for last 24 hours
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_scrapes,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_scrapes
                FROM scrape_logs 
                WHERE scraped_at >= datetime('now', '-1 day')
            """)
            scrape_stats = dict(cursor.fetchone())
            
            # Get latest price count
            cursor.execute("""
                SELECT COUNT(*) as latest_prices
                FROM price_history 
                WHERE scraped_at >= datetime('now', '-1 day')
            """)
            price_stats = dict(cursor.fetchone())
            
            return {
                'scrape_stats': scrape_stats,
                'price_stats': price_stats,
                'last_updated': datetime.now().isoformat()
            }
    
    def get_all_urls(self) -> List[Dict[str, Any]]:
        """Get all SKU-retailer URL mappings with details (including inactive ones)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sru.*, sc.brand, sc.product_name, sc.pack_size,
                       rc.name as retailer_name, sru.active as is_active,
                       sru.product_url as url
                FROM sku_retailer_urls sru
                JOIN sku_config sc ON sru.sku_id = sc.id
                JOIN retailer_config rc ON sru.retailer_id = rc.id
                ORDER BY sru.active DESC, sc.brand, sc.product_name, rc.name
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def add_url(self, sku_id: int, retailer_id: int, url: str, is_active: bool = True) -> bool:
        """Add a new SKU-retailer URL mapping."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if this SKU-retailer combination already exists (including inactive ones)
                cursor.execute("""
                    SELECT id, active, product_url FROM sku_retailer_urls
                    WHERE sku_id = ? AND retailer_id = ?
                """, (sku_id, retailer_id))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    cursor.execute("""
                        UPDATE sku_retailer_urls
                        SET product_url = ?, active = ?, updated_at = datetime('now')
                        WHERE sku_id = ? AND retailer_id = ?
                    """, (url, 1 if is_active else 0, sku_id, retailer_id))
                    print(f"Updated existing URL mapping (was active: {existing[1]})")
                else:
                    # Insert new record
                    cursor.execute("""
                        INSERT INTO sku_retailer_urls
                        (sku_id, retailer_id, product_url, active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (sku_id, retailer_id, url, 1 if is_active else 0))
                    print(f"Inserted new URL mapping")
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding URL: {e}")
            # Provide more specific error information
            if "UNIQUE constraint failed" in str(e):
                raise Exception(f"This product-retailer combination already exists in the database")
            else:
                raise Exception(f"Database error: {str(e)}")
    
    def update_url(self, sku_id: int, retailer_id: int, url: str, is_active: bool = True) -> bool:
        """Update an existing SKU-retailer URL mapping."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sku_retailer_urls
                    SET product_url = ?, active = ?, updated_at = datetime('now')
                    WHERE sku_id = ? AND retailer_id = ?
                """, (url, 1 if is_active else 0, sku_id, retailer_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating URL: {e}")
            return False
    
    def remove_url(self, sku_id: int, retailer_id: int) -> bool:
        """Remove a SKU-retailer URL mapping."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM sku_retailer_urls
                    WHERE sku_id = ? AND retailer_id = ?
                """, (sku_id, retailer_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing URL: {e}")
    
    # Schedule Configuration Methods
    def get_schedule_config(self) -> Dict[str, Any]:
        """Get the current schedule configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schedule_config ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                return dict(result)
            else:
                # Return default configuration
                return {
                    'schedule_enabled': False,
                    'schedule_time': '09:00',
                    'schedule_timezone': 'UTC',
                    'last_run': None,
                    'next_run': None
                }
    
    def update_schedule_config(self, enabled: bool, schedule_time: str = None, timezone: str = 'UTC') -> bool:
        """Update the schedule configuration."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if config exists
                cursor.execute("SELECT id FROM schedule_config ORDER BY id DESC LIMIT 1")
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing configuration
                    if schedule_time:
                        cursor.execute("""
                            UPDATE schedule_config 
                            SET schedule_enabled = ?, schedule_time = ?, schedule_timezone = ?, 
                                updated_at = datetime('now')
                            WHERE id = ?
                        """, (enabled, schedule_time, timezone, existing[0]))
                    else:
                        cursor.execute("""
                            UPDATE schedule_config 
                            SET schedule_enabled = ?, updated_at = datetime('now')
                            WHERE id = ?
                        """, (enabled, existing[0]))
                else:
                    # Insert new configuration
                    cursor.execute("""
                        INSERT INTO schedule_config 
                        (schedule_enabled, schedule_time, schedule_timezone, created_at, updated_at)
                        VALUES (?, ?, ?, datetime('now'), datetime('now'))
                    """, (enabled, schedule_time or '09:00', timezone))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating schedule config: {e}")
            return False
    
    def update_schedule_run_times(self, last_run: str = None, next_run: str = None) -> bool:
        """Update the last and next run times for the schedule."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get or create schedule config
                cursor.execute("SELECT id FROM schedule_config ORDER BY id DESC LIMIT 1")
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE schedule_config 
                        SET last_run = ?, next_run = ?, updated_at = datetime('now')
                        WHERE id = ?
                    """, (last_run, next_run, existing[0]))
                else:
                    cursor.execute("""
                        INSERT INTO schedule_config 
                        (schedule_enabled, schedule_time, last_run, next_run, created_at, updated_at)
                        VALUES (0, '09:00', ?, ?, datetime('now'), datetime('now'))
                    """, (last_run, next_run))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating schedule run times: {e}")
            return False
    
    def save_price_data(self, sku_id: int, retailer_id: int, price: float, 
                       currency: str = 'GBP', in_stock: bool = True, 
                       availability_text: str = None, product_title: str = None,
                       raw_data: str = None) -> int:
        """Save scraped price data to the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_history 
                (sku_id, retailer_id, price, currency, in_stock, availability_text, 
                 product_title, raw_data, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (sku_id, retailer_id, price, currency, in_stock, 
                  availability_text, product_title, raw_data))
            return cursor.lastrowid
            return False