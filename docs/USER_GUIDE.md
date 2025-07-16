# Price Tracker User Guide

## Overview

The Price Tracker system automatically monitors and tracks prices for over-the-counter (OTC) pain relief medications across multiple UK retailers. This guide will help you set up, configure, and use the system effectively.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Running the System](#running-the-system)
4. [Using the Dashboard](#using-the-dashboard)
5. [Data Export](#data-export)
6. [Monitoring and Health](#monitoring-and-health)
7. [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Python 3.9 or higher
- Windows 10/11, macOS, or Linux
- At least 2GB of available disk space
- Internet connection for web scraping

### Step 1: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Step 2: Initialize Database

```bash
# Run database migration to set up tables and initial data
python src/database/migrations.py
```

## Configuration

### SKU Configuration

Edit [`config/skus.json`](../config/skus.json) to add or modify products to track:

```json
{
  "skus": [
    {
      "id": 1,
      "brand": "Flarin",
      "product_name": "Flarin Joint & Muscular Pain Relief",
      "pack_size": "12s",
      "formulation": "200mg Ibuprofen",
      "category": "Anti-inflammatory",
      "active": true
    }
  ]
}
```

**Fields:**
- `id`: Unique identifier for the SKU
- `brand`: Brand name (e.g., "Flarin", "Nurofen")
- `product_name`: Full product name
- `pack_size`: Package size (e.g., "12s", "16s", "100ml")
- `formulation`: Active ingredients and strength
- `category`: Product category for grouping
- `active`: Set to `false` to disable tracking

### Retailer Configuration

Edit [`config/retailers.json`](../config/retailers.json) to configure retailers:

```json
{
  "retailers": [
    {
      "id": 1,
      "name": "Tesco",
      "base_url": "https://www.tesco.com",
      "scraper_module": "tesco_scraper",
      "selectors": {
        "price": "[data-testid='price-details'] .value",
        "availability": "[data-testid='product-availability']",
        "product_title": "[data-testid='product-title']"
      },
      "wait_selectors": ["[data-testid='price-details']"],
      "active": true
    }
  ]
}
```

**Fields:**
- `name`: Retailer display name
- `base_url`: Retailer's website URL
- `scraper_module`: Scraper implementation to use
- `selectors`: CSS selectors for extracting data
- `wait_selectors`: Elements to wait for before scraping
- `active`: Enable/disable retailer

### System Settings

Edit [`config/settings.ini`](../config/settings.ini) for system configuration:

```ini
[scraping]
default_delay_min = 2
default_delay_max = 8
request_timeout = 30
max_retries = 3
concurrent_scrapers = 3

[export]
default_format = xlsx
export_path = exports/

[dashboard]
host = localhost
port = 8501
```

## Running the System

### Manual Scraping

Run a one-time scrape of all configured products:

```bash
python src/main.py
```

### Scheduled Scraping

Start the automated scheduler for daily scraping:

```bash
python src/scheduler.py
```

The scheduler will:
- Run daily scrapes at 9:00 AM
- Perform health checks every 6 hours
- Run data quality checks every 12 hours

### Dashboard

Launch the interactive web dashboard:

```bash
streamlit run src/dashboard/app.py
```

Access the dashboard at: http://localhost:8501

## Using the Dashboard

### Dashboard Overview

The dashboard provides six main sections:

#### 📊 Dashboard
- **Key Metrics**: Active SKUs, retailers, recent prices, system status
- **Recent Price Data**: Latest scraped prices with filtering options
- **Quick Statistics**: Average prices, stock availability, product counts

#### 💰 Price Analysis
- **Price Comparison Charts**: Box plots showing price distribution by brand and retailer
- **Price Comparison Table**: Side-by-side price comparison across retailers
- **Cheapest/Most Expensive**: Identify best and worst deals

#### 📈 Trends
- **Historical Price Charts**: Line charts showing price trends over time
- **Product Selection**: Choose specific products for trend analysis
- **Price Statistics**: Current averages, daily changes, volatility metrics

#### 🔍 Health Monitor
- **System Status**: Overall health indicator with issue alerts
- **Scraping Health**: Success rates, response times, attempt counts
- **Data Freshness**: Age of data, stale data percentage
- **Database Health**: Connection status, record counts, database size

#### 📤 Export Data
- **Export Options**: Latest prices, price history, comparisons, health reports
- **Format Selection**: Excel (.xlsx) or CSV formats
- **Export History**: View and download previously generated exports

#### ⚙️ System Control
- **Scheduler Status**: View scheduler state and last run times
- **Manual Controls**: Trigger immediate scrapes, health checks, quality checks

### Navigation Tips

- Use the sidebar to switch between sections
- Apply filters to focus on specific brands or retailers
- Refresh data using the refresh buttons when needed
- Download exports directly from the dashboard

## Data Export

### Export Types

1. **Latest Prices**: Current prices for all products
2. **Price History**: Historical price data with trends
3. **Price Comparison**: Side-by-side retailer comparison
4. **Health Report**: System performance and quality metrics
5. **Power BI Dataset**: Formatted for business intelligence tools

### Export Formats

- **Excel (.xlsx)**: Formatted spreadsheets with multiple sheets
- **CSV**: Simple comma-separated values for data analysis

### Programmatic Export

```python
from src.utils.export_manager import ExportManager
from src.database.models import DatabaseManager

# Initialize components
db_manager = DatabaseManager()
export_manager = ExportManager(db_manager, {'export_path': 'exports/'})

# Export latest prices
filepath = export_manager.export_latest_prices(days=7, format='xlsx')
print(f"Export saved to: {filepath}")
```

## Monitoring and Health

### Health Indicators

The system monitors several health metrics:

- **Scrape Success Rate**: Percentage of successful scraping attempts
- **Data Freshness**: How recent the price data is
- **Error Rates**: Frequency of scraping failures by retailer
- **Database Health**: Connection status and data integrity

### Health Status Levels

- 🟢 **Healthy**: All systems operating normally
- 🟡 **Degraded**: Some issues detected but system functional
- 🔴 **Unhealthy**: Significant problems requiring attention

### Alerts and Notifications

The system logs important events and can be configured for:
- Email notifications (future enhancement)
- Slack alerts (future enhancement)
- Log file monitoring

### Log Files

Monitor system activity through log files:
- `logs/price_tracker.log`: Main application logs
- `logs/dashboard.log`: Dashboard-specific logs

## Troubleshooting

### Common Issues

#### 1. Scraping Failures

**Symptoms**: Low success rates, "Failed to navigate" errors

**Solutions**:
- Check internet connection
- Verify retailer URLs are still valid
- Update CSS selectors if website layouts changed
- Increase timeout values in settings

#### 2. Database Issues

**Symptoms**: "Database not accessible" errors

**Solutions**:
- Ensure database file permissions are correct
- Check available disk space
- Run database migration script
- Verify SQLite installation

#### 3. Dashboard Not Loading

**Symptoms**: Dashboard won't start or shows errors

**Solutions**:
- Check if port 8501 is available
- Verify all dependencies are installed
- Check Python path includes src directory
- Review dashboard logs for specific errors

#### 4. Export Failures

**Symptoms**: Export operations fail or produce empty files

**Solutions**:
- Ensure export directory exists and is writable
- Check if data exists for the selected time period
- Verify pandas and openpyxl are installed correctly

### Performance Optimization

#### Scraping Performance
- Reduce `concurrent_scrapers` if experiencing timeouts
- Increase delay times for slower websites
- Use retailer-specific scrapers for better reliability

#### Database Performance
- Regular database maintenance (vacuum, reindex)
- Monitor database size and implement archiving
- Consider PostgreSQL for high-volume deployments

#### Dashboard Performance
- Use data caching (already implemented)
- Limit historical data ranges for large datasets
- Consider pagination for very large result sets

### Getting Help

1. **Check Logs**: Review log files for detailed error messages
2. **Health Dashboard**: Use the health monitor to identify issues
3. **Test Components**: Run individual components to isolate problems
4. **Documentation**: Refer to technical documentation for advanced configuration

### Maintenance Tasks

#### Daily
- Monitor health dashboard for alerts
- Check scrape success rates
- Review any failed scraping attempts

#### Weekly
- Export and backup price data
- Review data quality reports
- Update product URLs if needed

#### Monthly
- Update SKU and retailer configurations
- Review and archive old log files
- Performance optimization review

## Advanced Configuration

### Custom Scrapers

To add support for new retailers, create a custom scraper:

```python
from src.scrapers.base_scraper import BaseScraper

class CustomRetailerScraper(BaseScraper):
    async def scrape_product(self, url, sku_data):
        # Implement custom scraping logic
        return {
            'success': True,
            'price': 9.99,
            'in_stock': True,
            'product_title': 'Product Name'
        }

# Register the scraper
from src.scrapers.scraper_factory import ScraperFactory
ScraperFactory.register_scraper('custom_scraper', CustomRetailerScraper)
```

### Database Customization

Extend the database schema for additional data:

```python
# Add custom fields to price_history table
cursor.execute("""
    ALTER TABLE price_history 
    ADD COLUMN custom_field TEXT
""")
```

### API Integration

The system can be extended with REST API endpoints for external integration:

```python
from flask import Flask, jsonify
from src.database.models import DatabaseManager

app = Flask(__name__)
db_manager = DatabaseManager()

@app.route('/api/prices/latest')
def get_latest_prices():
    prices = db_manager.get_latest_prices(7)
    return jsonify(prices)
```

This completes the user guide. The system is designed to be user-friendly while providing powerful features for price monitoring and analysis.