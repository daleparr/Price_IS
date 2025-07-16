"""
Export functionality for price tracker data.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)


class ExportManager:
    """Manages data export functionality."""
    
    def __init__(self, db_manager, settings: Dict[str, Any]):
        self.db_manager = db_manager
        self.settings = settings
        self.export_path = Path(settings.get('export_path', 'exports/'))
        self.export_path.mkdir(parents=True, exist_ok=True)
        
    def export_latest_prices(self, days: int = 7, format: str = 'xlsx') -> str:
        """Export latest prices to Excel or CSV."""
        try:
            # Get latest price data
            price_data = self.db_manager.get_latest_prices(days)
            
            if not price_data:
                logger.warning("No price data found for export")
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(price_data)
            
            # Add calculated columns
            df['scraped_date'] = pd.to_datetime(df['scraped_at']).dt.date
            df['scraped_time'] = pd.to_datetime(df['scraped_at']).dt.time
            
            # Reorder columns for better readability
            column_order = [
                'brand', 'product_name', 'pack_size', 'retailer_name',
                'price', 'currency', 'in_stock', 'availability_text',
                'scraped_date', 'scraped_time', 'product_title'
            ]
            
            # Only include columns that exist
            available_columns = [col for col in column_order if col in df.columns]
            df = df[available_columns]
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"price_data_{timestamp}.{format}"
            filepath = self.export_path / filename
            
            # Export based on format
            if format.lower() == 'xlsx':
                df.to_excel(filepath, index=False, engine='openpyxl')
            elif format.lower() == 'csv':
                df.to_csv(filepath, index=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
            logger.info(f"Exported {len(df)} price records to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error exporting latest prices: {str(e)}")
            raise
            
    def export_price_history(self, sku_id: int = None, retailer_id: int = None, 
                           days: int = 30, format: str = 'xlsx') -> str:
        """Export price history for specific SKU/retailer or all."""
        try:
            with self.db_manager.get_connection() as conn:
                # Build query based on filters
                where_conditions = ["ph.scraped_at >= datetime('now', '-{} days')".format(days)]
                params = []
                
                if sku_id:
                    where_conditions.append("ph.sku_id = ?")
                    params.append(sku_id)
                    
                if retailer_id:
                    where_conditions.append("ph.retailer_id = ?")
                    params.append(retailer_id)
                    
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT 
                        ph.*,
                        sc.brand,
                        sc.product_name,
                        sc.pack_size,
                        sc.formulation,
                        sc.category,
                        rc.name as retailer_name
                    FROM price_history ph
                    JOIN sku_config sc ON ph.sku_id = sc.id
                    JOIN retailer_config rc ON ph.retailer_id = rc.id
                    WHERE {where_clause}
                    ORDER BY ph.scraped_at DESC
                """
                
                df = pd.read_sql_query(query, conn, params=params)
                
            if df.empty:
                logger.warning("No price history data found for export")
                return None
                
            # Process datetime columns
            df['scraped_date'] = pd.to_datetime(df['scraped_at']).dt.date
            df['scraped_time'] = pd.to_datetime(df['scraped_at']).dt.time
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = ""
            if sku_id:
                suffix += f"_sku{sku_id}"
            if retailer_id:
                suffix += f"_retailer{retailer_id}"
                
            filename = f"price_history{suffix}_{timestamp}.{format}"
            filepath = self.export_path / filename
            
            # Export
            if format.lower() == 'xlsx':
                df.to_excel(filepath, index=False, engine='openpyxl')
            elif format.lower() == 'csv':
                df.to_csv(filepath, index=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
            logger.info(f"Exported {len(df)} price history records to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error exporting price history: {str(e)}")
            raise
            
    def export_price_comparison(self, days: int = 7, format: str = 'xlsx') -> str:
        """Export price comparison across retailers."""
        try:
            with self.db_manager.get_connection() as conn:
                # Get latest price for each SKU-retailer combination
                query = """
                    WITH latest_prices AS (
                        SELECT 
                            sku_id,
                            retailer_id,
                            price,
                            in_stock,
                            ROW_NUMBER() OVER (
                                PARTITION BY sku_id, retailer_id 
                                ORDER BY scraped_at DESC
                            ) as rn
                        FROM price_history
                        WHERE scraped_at >= datetime('now', '-{} days')
                        AND price IS NOT NULL
                    )
                    SELECT 
                        sc.brand,
                        sc.product_name,
                        sc.pack_size,
                        rc.name as retailer_name,
                        lp.price,
                        lp.in_stock
                    FROM latest_prices lp
                    JOIN sku_config sc ON lp.sku_id = sc.id
                    JOIN retailer_config rc ON lp.retailer_id = rc.id
                    WHERE lp.rn = 1
                    ORDER BY sc.brand, sc.product_name, lp.price
                """.format(days)
                
                df = pd.read_sql_query(query, conn)
                
            if df.empty:
                logger.warning("No price comparison data found")
                return None
                
            # Create pivot table for comparison
            pivot_df = df.pivot_table(
                index=['brand', 'product_name', 'pack_size'],
                columns='retailer_name',
                values='price',
                aggfunc='first'
            ).reset_index()
            
            # Add price statistics
            price_columns = [col for col in pivot_df.columns if col not in ['brand', 'product_name', 'pack_size']]
            pivot_df['min_price'] = pivot_df[price_columns].min(axis=1)
            pivot_df['max_price'] = pivot_df[price_columns].max(axis=1)
            pivot_df['avg_price'] = pivot_df[price_columns].mean(axis=1).round(2)
            pivot_df['price_range'] = (pivot_df['max_price'] - pivot_df['min_price']).round(2)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"price_comparison_{timestamp}.{format}"
            filepath = self.export_path / filename
            
            # Export
            if format.lower() == 'xlsx':
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    # Write comparison table
                    pivot_df.to_excel(writer, sheet_name='Price Comparison', index=False)
                    
                    # Write raw data
                    df.to_excel(writer, sheet_name='Raw Data', index=False)
                    
            elif format.lower() == 'csv':
                pivot_df.to_csv(filepath, index=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
            logger.info(f"Exported price comparison to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error exporting price comparison: {str(e)}")
            raise
            
    def export_health_report(self, format: str = 'xlsx') -> str:
        """Export system health and quality report."""
        try:
            # Get health data
            with self.db_manager.get_connection() as conn:
                # Scrape logs summary
                scrape_logs_query = """
                    SELECT 
                        DATE(scraped_at) as scrape_date,
                        rc.name as retailer_name,
                        status,
                        COUNT(*) as count,
                        AVG(response_time) as avg_response_time
                    FROM scrape_logs sl
                    JOIN retailer_config rc ON sl.retailer_id = rc.id
                    WHERE scraped_at >= datetime('now', '-30 days')
                    GROUP BY DATE(scraped_at), rc.name, status
                    ORDER BY scrape_date DESC, retailer_name
                """
                
                scrape_df = pd.read_sql_query(scrape_logs_query, conn)
                
                # Health metrics
                health_metrics_query = """
                    SELECT 
                        DATE(recorded_at) as metric_date,
                        metric_name,
                        metric_value,
                        metric_text
                    FROM health_metrics
                    WHERE recorded_at >= datetime('now', '-30 days')
                    ORDER BY recorded_at DESC
                """
                
                health_df = pd.read_sql_query(health_metrics_query, conn)
                
                # Data freshness by SKU/retailer
                freshness_query = """
                    SELECT 
                        sc.brand,
                        sc.product_name,
                        rc.name as retailer_name,
                        MAX(ph.scraped_at) as last_scraped,
                        COUNT(ph.id) as total_records
                    FROM sku_config sc
                    CROSS JOIN retailer_config rc
                    LEFT JOIN price_history ph ON sc.id = ph.sku_id AND rc.id = ph.retailer_id
                    WHERE sc.active = 1 AND rc.active = 1
                    GROUP BY sc.id, rc.id
                    ORDER BY last_scraped DESC
                """
                
                freshness_df = pd.read_sql_query(freshness_query, conn)
                
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"health_report_{timestamp}.{format}"
            filepath = self.export_path / filename
            
            # Export
            if format.lower() == 'xlsx':
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    scrape_df.to_excel(writer, sheet_name='Scrape Logs', index=False)
                    health_df.to_excel(writer, sheet_name='Health Metrics', index=False)
                    freshness_df.to_excel(writer, sheet_name='Data Freshness', index=False)
                    
            elif format.lower() == 'csv':
                # Export multiple CSV files
                base_path = filepath.with_suffix('')
                scrape_df.to_csv(f"{base_path}_scrape_logs.csv", index=False)
                health_df.to_csv(f"{base_path}_health_metrics.csv", index=False)
                freshness_df.to_csv(f"{base_path}_data_freshness.csv", index=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
            logger.info(f"Exported health report to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error exporting health report: {str(e)}")
            raise
            
    def export_power_bi_dataset(self) -> str:
        """Export data in Power BI friendly format."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"powerbi_dataset_{timestamp}.xlsx"
            filepath = self.export_path / filename
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Price history table
                with self.db_manager.get_connection() as conn:
                    price_query = """
                        SELECT 
                            ph.id as price_id,
                            ph.sku_id,
                            ph.retailer_id,
                            ph.price,
                            ph.currency,
                            ph.in_stock,
                            ph.scraped_at,
                            sc.brand,
                            sc.product_name,
                            sc.pack_size,
                            sc.formulation,
                            sc.category,
                            rc.name as retailer_name,
                            rc.base_url as retailer_url
                        FROM price_history ph
                        JOIN sku_config sc ON ph.sku_id = sc.id
                        JOIN retailer_config rc ON ph.retailer_id = rc.id
                        WHERE ph.scraped_at >= datetime('now', '-90 days')
                        ORDER BY ph.scraped_at DESC
                    """
                    
                    price_df = pd.read_sql_query(price_query, conn)
                    price_df.to_excel(writer, sheet_name='PriceHistory', index=False)
                    
                    # SKU dimension table
                    sku_query = """
                        SELECT 
                            id as sku_id,
                            brand,
                            product_name,
                            pack_size,
                            formulation,
                            category,
                            active,
                            created_at
                        FROM sku_config
                    """
                    
                    sku_df = pd.read_sql_query(sku_query, conn)
                    sku_df.to_excel(writer, sheet_name='SKUs', index=False)
                    
                    # Retailer dimension table
                    retailer_query = """
                        SELECT 
                            id as retailer_id,
                            name as retailer_name,
                            base_url,
                            active,
                            created_at
                        FROM retailer_config
                    """
                    
                    retailer_df = pd.read_sql_query(retailer_query, conn)
                    retailer_df.to_excel(writer, sheet_name='Retailers', index=False)
                    
                    # Date dimension (for time intelligence)
                    start_date = datetime.now() - timedelta(days=365)
                    end_date = datetime.now() + timedelta(days=30)
                    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                    
                    date_df = pd.DataFrame({
                        'Date': date_range,
                        'Year': date_range.year,
                        'Month': date_range.month,
                        'Day': date_range.day,
                        'Quarter': date_range.quarter,
                        'WeekOfYear': date_range.isocalendar().week,
                        'DayOfWeek': date_range.dayofweek,
                        'MonthName': date_range.strftime('%B'),
                        'DayName': date_range.strftime('%A')
                    })
                    
                    date_df.to_excel(writer, sheet_name='DateDimension', index=False)
                    
            logger.info(f"Exported Power BI dataset to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error exporting Power BI dataset: {str(e)}")
            raise
            
    def get_export_history(self) -> List[Dict[str, Any]]:
        """Get list of previously generated exports."""
        try:
            exports = []
            for file_path in self.export_path.glob("*"):
                if file_path.is_file():
                    stat = file_path.stat()
                    exports.append({
                        'filename': file_path.name,
                        'filepath': str(file_path),
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    
            # Sort by creation time, newest first
            exports.sort(key=lambda x: x['created_at'], reverse=True)
            return exports
            
        except Exception as e:
            logger.error(f"Error getting export history: {str(e)}")
            return []