# Technical Documentation

## Architecture Overview

The Price Tracker system is built using a modular architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dashboard     │    │   Scheduler     │    │   CLI Tools     │
│  (Streamlit)    │    │   (Schedule)    │    │   (Manual)      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────────┐
                    │     Main Orchestrator       │
                    │    (PriceTrackerOrchestrator)│
                    └─────────────┬───────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
┌─────────▼───────┐    ┌─────────▼───────┐    ┌─────────▼───────┐
│   Scrapers      │    │   Database      │    │   Utilities     │
│   (Playwright)  │    │   (SQLite)      │    │ (Validation,    │
│                 │    │                 │    │  Export, etc.)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Core Components

### 1. Database Layer (`src/database/`)

#### DatabaseManager (`models.py`)
- **Purpose**: Manages all database operations and schema
- **Key Methods**:
  - `create_tables()`: Initialize database schema
  - `insert_price_data()`: Store scraped price information
  - `get_latest_prices()`: Retrieve recent price data
  - `log_scrape_attempt()`: Record scraping attempts and results

#### Database Schema
```sql
-- Core configuration tables
sku_config: Product definitions and metadata
retailer_config: Retailer information and scraping configuration
sku_retailer_urls: URL mappings between products and retailers

-- Data tables
price_history: Historical price data with timestamps
scrape_logs: Detailed logging of all scraping attempts
health_metrics: System performance and health metrics
```

### 2. Scraping Engine (`src/scrapers/`)

#### BaseScraper (`base_scraper.py`)
- **Purpose**: Abstract base class providing common scraping functionality
- **Key Features**:
  - Playwright browser automation with stealth capabilities
  - Anti-bot detection measures (user agent rotation, delays, etc.)
  - Error handling and retry logic
  - Generic price and availability extraction

#### Retailer-Specific Scrapers
- **TescoScraper**: Handles Tesco-specific website structure and elements
- **SainsburysScraper**: Manages Sainsbury's website peculiarities
- **GenericScraper**: Fallback scraper for retailers without specific implementations

#### ScraperFactory (`scraper_factory.py`)
- **Purpose**: Factory pattern for creating appropriate scraper instances
- **Features**:
  - Dynamic scraper registration
  - Automatic fallback to generic scraper
  - Configuration-driven scraper selection

### 3. Data Processing (`src/utils/`)

#### PriceValidator (`data_validator.py`)
- **Purpose**: Validates and cleans scraped data
- **Validation Rules**:
  - Price range validation (£0.01 - £1000.00)
  - Availability status normalization
  - Product title sanitization
  - Response time validation

#### DataQualityChecker (`data_validator.py`)
- **Purpose**: Monitors data quality and identifies anomalies
- **Features**:
  - Price anomaly detection (spikes/drops > 20%)
  - Data freshness monitoring
  - Comprehensive quality reporting

#### HealthMonitor (`health_monitor.py`)
- **Purpose**: System health monitoring and alerting
- **Metrics Tracked**:
  - Scrape success rates
  - Response times
  - Error frequencies by retailer
  - Database health and connectivity

#### ExportManager (`export_manager.py`)
- **Purpose**: Data export functionality
- **Export Types**:
  - Latest prices (Excel/CSV)
  - Historical price data
  - Price comparison matrices
  - System health reports
  - Power BI datasets

### 4. Orchestration (`src/`)

#### PriceTrackerOrchestrator (`main.py`)
- **Purpose**: Main coordination of scraping operations
- **Responsibilities**:
  - Load configuration from JSON files
  - Coordinate scraper instances
  - Manage concurrent scraping with semaphores
  - Validate and store results
  - Generate summary reports

#### PriceTrackerScheduler (`scheduler.py`)
- **Purpose**: Automated scheduling of operations
- **Schedule**:
  - Daily scrapes at 9:00 AM
  - Health checks every 6 hours
  - Data quality checks every 12 hours
- **Features**:
  - Background thread execution
  - Signal handling for graceful shutdown
  - Manual operation triggers

### 5. User Interface (`src/dashboard/`)

#### Streamlit Dashboard (`app.py`)
- **Purpose**: Web-based user interface
- **Pages**:
  - **Dashboard**: Overview and key metrics
  - **Price Analysis**: Comparison charts and tables
  - **Trends**: Historical price visualization
  - **Health Monitor**: System status and diagnostics
  - **Export Data**: Data export interface
  - **System Control**: Manual operation controls

## Configuration System

### SKU Configuration (`config/skus.json`)
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

### Retailer Configuration (`config/retailers.json`)
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
        "availability": "[data-testid='product-availability']"
      },
      "wait_selectors": ["[data-testid='price-details']"],
      "active": true
    }
  ]
}
```

### System Settings (`config/settings.ini`)
```ini
[scraping]
default_delay_min = 2
default_delay_max = 8
request_timeout = 30
max_retries = 3
concurrent_scrapers = 3

[database]
db_path = data/price_tracker.db

[export]
default_format = xlsx
export_path = exports/
```

## Anti-Bot Measures

### Browser Configuration
- **Stealth Mode**: Removes automation indicators
- **User Agent Rotation**: Random, realistic user agents
- **Viewport Randomization**: Varies browser window size
- **Request Headers**: Realistic HTTP headers

### Behavioral Patterns
- **Random Delays**: 2-8 seconds between requests
- **Human-like Navigation**: Proper page loading waits
- **Retry Logic**: Exponential backoff on failures
- **Session Management**: Proper cookie handling

### Code Example
```python
# Browser launch with stealth options
launch_options = {
    'headless': True,
    'args': [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled'
    ]
}

# Context with realistic settings
context_options = {
    'viewport': {'width': 1366, 'height': 768},
    'user_agent': self.get_random_user_agent(),
    'locale': 'en-GB',
    'timezone_id': 'Europe/London'
}
```

## Data Flow

### Scraping Process
1. **Configuration Loading**: Load SKUs, retailers, and settings
2. **URL Mapping**: Retrieve product URLs from database
3. **Scraper Creation**: Factory creates appropriate scraper instances
4. **Concurrent Execution**: Semaphore-controlled parallel scraping
5. **Data Validation**: Validate and clean scraped data
6. **Storage**: Store validated data in database
7. **Health Logging**: Record scraping attempts and results
8. **Anomaly Detection**: Check for price anomalies
9. **Summary Generation**: Create operation summary

### Data Validation Pipeline
```python
# Example validation flow
raw_data = await scraper.scrape_product(url, sku_data)
is_valid, cleaned_data = price_validator.validate_price_data(raw_data)

if is_valid:
    price_id = db_manager.insert_price_data(...)
    anomalies = quality_checker.check_price_anomalies(...)
    health_monitor.log_scrape_attempt(status='success', ...)
else:
    health_monitor.log_scrape_attempt(status='failed', ...)
```

## Error Handling

### Scraping Errors
- **Network Issues**: Retry with exponential backoff
- **Element Not Found**: Try alternative selectors
- **Timeout**: Increase timeout and retry
- **Rate Limiting**: Implement longer delays

### Data Validation Errors
- **Invalid Prices**: Log error, skip record
- **Missing Data**: Attempt alternative extraction
- **Format Issues**: Apply data cleaning rules

### System Errors
- **Database Issues**: Retry connection, log errors
- **Configuration Errors**: Validate on startup
- **Resource Exhaustion**: Implement resource monitoring

## Performance Optimization

### Scraping Performance
- **Concurrent Execution**: Configurable parallelism (default: 3)
- **Connection Reuse**: Browser context reuse where possible
- **Selective Loading**: Only load necessary page elements
- **Caching**: Cache static configuration data

### Database Performance
- **Indexes**: Strategic indexing on frequently queried columns
- **Batch Operations**: Bulk inserts where possible
- **Connection Pooling**: Efficient connection management
- **Query Optimization**: Optimized SQL queries

### Memory Management
- **Browser Cleanup**: Proper browser resource disposal
- **Data Streaming**: Stream large datasets for export
- **Garbage Collection**: Explicit cleanup of large objects

## Security Considerations

### Data Protection
- **Local Storage**: All data stored locally in SQLite
- **No External APIs**: No data transmitted to external services
- **Access Control**: File system permissions for data protection

### Web Scraping Ethics
- **Respectful Scraping**: Reasonable delays between requests
- **robots.txt Compliance**: Respect where feasible
- **Rate Limiting**: Avoid overwhelming target servers
- **User Agent Honesty**: Realistic but not deceptive user agents

### System Security
- **Input Validation**: Validate all configuration inputs
- **SQL Injection Prevention**: Parameterized queries
- **Path Traversal Protection**: Validate file paths
- **Dependency Management**: Regular security updates

## Monitoring and Alerting

### Health Metrics
```python
health_status = {
    'overall_status': 'healthy|degraded|unhealthy',
    'scrape_health': {
        'success_rate': 95.5,
        'average_response_time': 2.3,
        'total_attempts': 150
    },
    'data_freshness': {
        'stale_percentage': 5.2,
        'oldest_data_age_hours': 18.5
    },
    'database': {
        'accessible': True,
        'total_records': 15420,
        'database_size_mb': 45.2
    }
}
```

### Alerting Thresholds
- **Success Rate < 80%**: System degraded
- **Success Rate < 50%**: System unhealthy
- **Stale Data > 20%**: Data freshness warning
- **Response Time > 10s**: Performance warning

## Testing Strategy

### Unit Tests (`tests/`)
- **Database Operations**: CRUD operations, schema validation
- **Scraper Components**: Price parsing, validation logic
- **Utility Functions**: Data validation, export functionality

### Integration Tests
- **End-to-End Scraping**: Full scraping workflow
- **Database Integration**: Multi-component data flow
- **Export Functionality**: Complete export processes

### Test Configuration
```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short --strict-markers
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
```

## Deployment

### Local Deployment
1. Install dependencies: `pip install -r requirements.txt`
2. Install browsers: `playwright install`
3. Initialize database: `python src/database/migrations.py`
4. Configure products and retailers
5. Start scheduler: `python src/scheduler.py`
6. Launch dashboard: `streamlit run src/dashboard/app.py`

### Production Considerations
- **Process Management**: Use systemd or supervisor for process management
- **Log Rotation**: Configure log rotation for long-running deployments
- **Backup Strategy**: Regular database backups
- **Monitoring**: External monitoring of system health
- **Resource Limits**: Configure appropriate resource limits

### Docker Deployment (Future Enhancement)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install --with-deps chromium
COPY . .
CMD ["python", "src/scheduler.py"]
```

## Extensibility

### Adding New Retailers
1. Create retailer-specific scraper class
2. Register scraper in factory
3. Add retailer configuration to JSON
4. Test scraper implementation

### Adding New Data Fields
1. Extend database schema
2. Update scraper extraction logic
3. Modify validation rules
4. Update export formats

### Custom Analytics
1. Extend database queries
2. Add dashboard visualizations
3. Create custom export formats
4. Implement alerting rules

## API Reference

### DatabaseManager Methods
```python
# Core operations
create_tables() -> None
insert_sku(brand, product_name, pack_size, ...) -> int
insert_retailer(name, base_url, scraper_module, ...) -> int
insert_price_data(sku_id, retailer_id, price, ...) -> int

# Data retrieval
get_active_skus() -> List[Dict]
get_active_retailers() -> List[Dict]
get_latest_prices(days=7) -> List[Dict]
get_health_summary() -> Dict
```

### Scraper Interface
```python
class BaseScraper(ABC):
    async def scrape_product(url: str, sku_data: Dict) -> Dict:
        """
        Returns:
        {
            'success': bool,
            'price': float,
            'in_stock': bool,
            'availability_text': str,
            'product_title': str,
            'error': str,
            'response_time': float
        }
        """
```

### Export Manager Methods
```python
export_latest_prices(days=7, format='xlsx') -> str
export_price_history(sku_id=None, retailer_id=None, days=30) -> str
export_price_comparison(days=7) -> str
export_health_report() -> str
export_power_bi_dataset() -> str
```

This technical documentation provides comprehensive coverage of the system architecture, implementation details, and operational considerations for the Price Tracker system.