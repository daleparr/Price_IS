# Retail Price Tracker for OTC Pain Relief Brands

A scalable system to track daily pricing for over-the-counter (OTC) pain relief SKUs across UK retailers.

## Features

- Automated daily price collection using Playwright
- Configurable SKUs and retailers
- SQLite database for local storage
- Streamlit dashboard with filtering and visualization
- Excel/CSV export functionality
- Health monitoring and error logging
- Anti-bot measures with stealth capabilities

## Project Structure

```
price_tracker/
├── config/                   # Configuration files
├── src/                     # Source code
│   ├── scrapers/           # Retailer-specific scrapers
│   ├── database/           # Database operations
│   ├── utils/              # Utility functions
│   └── dashboard/          # Streamlit dashboard
├── data/                   # SQLite database
├── exports/                # Generated exports
├── logs/                   # Application logs
└── tests/                  # Test files
```

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

2. Initialize the database:
   ```bash
   python src/database/migrations.py
   ```

3. Configure SKUs and retailers in `config/` directory

4. Run the scraper:
   ```bash
   python src/main.py
   ```

5. Launch the dashboard:
   ```bash
   streamlit run src/dashboard/app.py
   ```

## Configuration

- `config/skus.json` - Product configuration
- `config/retailers.json` - Retailer configuration
- `config/settings.ini` - Application settings

## Tracked Brands

- Flarin (12s, 16s)
- Anadin (Regular, Joint Pain)
- Nurofen (8hr 256mg, Oral)
- Nuromol
- Panadol
- Voltarol
- Ibuleve
- Solpadeine

## Tracked Retailers

- Tesco
- Sainsbury's
- Morrisons
- Boots
- Wilko
- Superdrug
- Waitrose
- Ocado
- Amazon

## License

Proprietary - Flarin Pain Relief Company