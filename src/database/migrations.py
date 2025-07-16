"""
Database migration script to initialize the price tracker database.
"""

import json
import logging
from pathlib import Path
from src.database.models import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config_data():
    """Load SKU and retailer configuration from JSON files."""
    config_dir = Path("config")
    
    # Load SKUs
    with open(config_dir / "skus.json", "r") as f:
        skus_data = json.load(f)
    
    # Load retailers
    with open(config_dir / "retailers.json", "r") as f:
        retailers_data = json.load(f)
    
    return skus_data, retailers_data


def populate_initial_data(db_manager: DatabaseManager):
    """Populate database with initial SKU and retailer data."""
    skus_data, retailers_data = load_config_data()
    
    # Insert SKUs
    logger.info("Inserting SKU configurations...")
    for sku in skus_data["skus"]:
        if sku["active"]:
            db_manager.insert_sku(
                brand=sku["brand"],
                product_name=sku["product_name"],
                pack_size=sku["pack_size"],
                formulation=sku.get("formulation"),
                category=sku.get("category")
            )
    
    # Insert retailers
    logger.info("Inserting retailer configurations...")
    for retailer in retailers_data["retailers"]:
        if retailer["active"]:
            db_manager.insert_retailer(
                name=retailer["name"],
                base_url=retailer["base_url"],
                scraper_module=retailer["scraper_module"],
                selectors=json.dumps(retailer.get("selectors", {})),
                wait_selectors=json.dumps(retailer.get("wait_selectors", []))
            )


def create_sample_url_mappings(db_manager: DatabaseManager):
    """Create sample URL mappings for testing purposes."""
    logger.info("Creating sample URL mappings...")
    
    # Get SKUs and retailers from database
    skus = db_manager.get_active_skus()
    retailers = db_manager.get_active_retailers()
    
    # Sample URL mappings (these would need to be populated with real URLs)
    sample_mappings = [
        # Flarin 12s examples
        {"sku_id": 1, "retailer_id": 1, "url": "https://www.tesco.com/groceries/en-GB/products/example-flarin-12s"},
        {"sku_id": 1, "retailer_id": 4, "url": "https://www.boots.com/flarin-joint-muscular-pain-relief-12-tablets-example"},
        
        # Nurofen examples
        {"sku_id": 5, "retailer_id": 1, "url": "https://www.tesco.com/groceries/en-GB/products/example-nurofen-8hr"},
        {"sku_id": 5, "retailer_id": 2, "url": "https://www.sainsburys.co.uk/gol-ui/product/example-nurofen-8hr"},
    ]
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        for mapping in sample_mappings:
            cursor.execute("""
                INSERT OR IGNORE INTO sku_retailer_urls (sku_id, retailer_id, product_url)
                VALUES (?, ?, ?)
            """, (mapping["sku_id"], mapping["retailer_id"], mapping["url"]))
        conn.commit()


def main():
    """Main migration function."""
    logger.info("Starting database migration...")
    
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Create tables
    logger.info("Creating database tables...")
    db_manager.create_tables()
    
    # Populate initial data
    populate_initial_data(db_manager)
    
    # Create sample URL mappings
    create_sample_url_mappings(db_manager)
    
    # Log health summary
    health = db_manager.get_health_summary()
    logger.info(f"Migration completed. Health summary: {health}")
    
    logger.info("Database migration completed successfully!")


if __name__ == "__main__":
    main()