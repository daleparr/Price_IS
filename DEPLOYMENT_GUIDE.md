# Deployment Guide - Price Tracker System

## Overview

This guide provides step-by-step instructions for deploying the Price Tracker system for Flarin. The system is designed for local deployment with minimal setup requirements.

## System Requirements

### Hardware Requirements
- **CPU**: Dual-core processor (2.0 GHz or higher)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB available disk space
- **Network**: Stable internet connection for web scraping

### Software Requirements
- **Operating System**: Windows 10/11, macOS 10.14+, or Linux Ubuntu 18.04+
- **Python**: Version 3.9 or higher
- **Browser**: Chromium (automatically installed with Playwright)

## Installation Steps

### Step 1: Prepare the Environment

1. **Download and extract** the Price Tracker system files to your desired directory
2. **Open a terminal/command prompt** in the project directory
3. **Verify Python installation**:
   ```bash
   python --version
   # Should show Python 3.9 or higher
   ```

### Step 2: Install Dependencies

1. **Install Python packages**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers**:
   ```bash
   playwright install
   ```
   
   This will download Chromium browser for web scraping.

### Step 3: Initialize the Database

1. **Run the database migration**:
   ```bash
   python src/database/migrations.py
   ```
   
   This creates the SQLite database and populates it with initial SKU and retailer data.

### Step 4: Configure Product URLs

**IMPORTANT**: Before running the system, you need to add actual product URLs.

1. **Edit the database** to add real product URLs:
   ```bash
   # You can use a SQLite browser tool or run Python commands
   python -c "
   from src.database.models import DatabaseManager
   db = DatabaseManager()
   
   # Example: Add URL for Flarin 12s at Tesco
   with db.get_connection() as conn:
       cursor = conn.cursor()
       cursor.execute('''
           INSERT INTO sku_retailer_urls (sku_id, retailer_id, product_url)
           VALUES (1, 1, 'https://www.tesco.com/groceries/en-GB/products/actual-flarin-url')
       ''')
       conn.commit()
   "
   ```

2. **Alternative**: Modify [`config/retailers.json`](config/retailers.json) and re-run migrations

## Running the System

### Option 1: Automated Scheduling (Recommended)

Start the automated scheduler for daily price tracking:

```bash
python src/scheduler.py
```

This will:
- Run daily scrapes at 9:00 AM
- Perform health checks every 6 hours
- Run data quality checks every 12 hours
- Keep running in the background

### Option 2: Manual Operation

Run a one-time scrape:

```bash
python src/main.py
```

### Option 3: Dashboard Only

Launch the web dashboard:

```bash
streamlit run src/dashboard/app.py
```

Access at: http://localhost:8501

## Configuration

### SKU Configuration

Edit [`config/skus.json`](config/skus.json) to modify tracked products:

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

### Retailer Configuration

Edit [`config/retailers.json`](config/retailers.json) to modify retailers and CSS selectors:

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
      "active": true
    }
  ]
}
```

### System Settings

Edit [`config/settings.ini`](config/settings.ini) for system behavior:

```ini
[scraping]
default_delay_min = 2
default_delay_max = 8
concurrent_scrapers = 3

[export]
export_path = exports/
default_format = xlsx
```

## Monitoring and Maintenance

### Health Monitoring

1. **Dashboard Health Page**: Monitor system status at http://localhost:8501
2. **Log Files**: Check `logs/price_tracker.log` for detailed activity
3. **Database**: Monitor `data/price_tracker.db` size and growth

### Regular Maintenance

#### Daily
- Check dashboard for scraping success rates
- Review any error alerts
- Verify data freshness

#### Weekly
- Export price data for backup
- Review and update product URLs if needed
- Check log file sizes

#### Monthly
- Update SKU configurations for new products
- Review retailer selector accuracy
- Archive old log files

## Troubleshooting

### Common Issues

#### 1. Scraping Failures
**Symptoms**: Low success rates, navigation errors

**Solutions**:
- Check internet connection
- Verify product URLs are still valid
- Update CSS selectors if website layouts changed
- Increase timeout values in settings

#### 2. Database Errors
**Symptoms**: "Database locked" or connection errors

**Solutions**:
- Ensure no other processes are using the database
- Check disk space availability
- Restart the system if needed

#### 3. Dashboard Not Loading
**Symptoms**: Streamlit errors or blank pages

**Solutions**:
- Check if port 8501 is available
- Verify all dependencies are installed
- Check Python path includes src directory

#### 4. Missing Dependencies
**Symptoms**: Import errors or module not found

**Solutions**:
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Reinstall Playwright
playwright install --force
```

### Performance Optimization

#### For High-Volume Scraping
- Reduce `concurrent_scrapers` to 1-2 for stability
- Increase delay times between requests
- Consider running during off-peak hours

#### For Large Datasets
- Implement data archiving strategy
- Use database vacuum operations
- Monitor disk space usage

## Security Considerations

### Data Protection
- All data stored locally in SQLite database
- No external data transmission
- Secure file system permissions recommended

### Web Scraping Ethics
- Respectful request timing (2-8 second delays)
- Reasonable concurrent request limits
- Monitor for rate limiting responses

## Backup and Recovery

### Database Backup
```bash
# Create backup
cp data/price_tracker.db data/price_tracker_backup_$(date +%Y%m%d).db

# Restore from backup
cp data/price_tracker_backup_YYYYMMDD.db data/price_tracker.db
```

### Configuration Backup
```bash
# Backup configurations
tar -czf config_backup_$(date +%Y%m%d).tar.gz config/
```

### Export Data
Use the dashboard export functionality or:
```bash
python -c "
from src.utils.export_manager import ExportManager
from src.database.models import DatabaseManager

db = DatabaseManager()
export_mgr = ExportManager(db, {'export_path': 'exports/'})
export_mgr.export_latest_prices(days=30, format='xlsx')
"
```

## Production Deployment

### Windows Service (Optional)
For production deployment, consider running as a Windows service:

1. Install `pywin32`: `pip install pywin32`
2. Create service wrapper script
3. Register with Windows Service Manager

### Linux Systemd (Optional)
For Linux production deployment:

1. Create systemd service file
2. Enable automatic startup
3. Configure log rotation

### Docker Deployment (Future)
The system is designed to be containerizable:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install --with-deps chromium
COPY . .
CMD ["python", "src/scheduler.py"]
```

## Support and Maintenance

### Log Analysis
Monitor these key log patterns:
- `Scrape successful`: Normal operation
- `Scrape failed`: Requires investigation
- `Health check`: System status updates
- `Export generated`: Data export activities

### Performance Metrics
Track these KPIs:
- Scrape success rate (target: >90%)
- Average response time (target: <5 seconds)
- Data freshness (target: <24 hours)
- System uptime (target: >99%)

### Escalation Procedures
1. **Low Success Rate (<80%)**: Check network and website changes
2. **System Errors**: Review logs and restart if needed
3. **Data Issues**: Validate configurations and URLs
4. **Performance Issues**: Optimize settings and resource allocation

## Contact Information

For technical support or questions about this deployment:
- **System Documentation**: See `docs/` directory
- **User Guide**: `docs/USER_GUIDE.md`
- **Technical Documentation**: `docs/TECHNICAL_DOCUMENTATION.md`

---

**Deployment Checklist**

- [ ] Python 3.9+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Playwright browsers installed (`playwright install`)
- [ ] Database initialized (`python src/database/migrations.py`)
- [ ] Product URLs configured
- [ ] System tested (`python test_basic_integration.py`)
- [ ] Scheduler started (`python src/scheduler.py`)
- [ ] Dashboard accessible (http://localhost:8501)
- [ ] Monitoring procedures established
- [ ] Backup strategy implemented

**System is ready for production use!**