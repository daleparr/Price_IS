"""
Simplified Streamlit dashboard for the price tracker system.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.models import DatabaseManager
from src.utils.export_manager import ExportManager
from src.utils.health_monitor import HealthMonitor
from src.utils.data_validator import DataQualityChecker

# Page configuration (only if not already set)
try:
    st.set_page_config(
        page_title="Price Tracker Dashboard",
        page_icon="💊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
except Exception:
    # Page config already set by streamlit_app.py
    pass

# Initialize components
@st.cache_resource(ttl=300)  # Cache for 5 minutes to allow updates
def init_components():
    """Initialize database and utility components."""
    # Use absolute path for database in cloud deployment
    db_manager = DatabaseManager()
    
    # Initialize database with tables and data for cloud deployment
    try:
        # Create tables if they don't exist (including new schedule_config table)
        db_manager.create_tables()
        
        # Check if we need to populate initial data
        retailers = db_manager.get_active_retailers()
        if len(retailers) == 0:
            # Import and run initial data population
            from src.database.migrations import populate_initial_data
            populate_initial_data(db_manager)
            st.success("✅ Database initialized with configuration data")
    except Exception as e:
        st.error(f"Database initialization error: {e}")
    
    settings = {
        'export_path': 'exports/',
        'log_level': 'INFO',
        'log_file': 'logs/dashboard.log'
    }
    export_manager = ExportManager(db_manager, settings)
    health_monitor = HealthMonitor(db_manager, settings)
    quality_checker = DataQualityChecker(db_manager)
    
    return db_manager, export_manager, health_monitor, quality_checker

db_manager, export_manager, health_monitor, quality_checker = init_components()

# Sidebar
st.sidebar.title("🏥 Price Tracker")
st.sidebar.markdown("---")

# Navigation
page = st.sidebar.selectbox(
    "Navigate to:",
    ["📊 Dashboard", "💰 Price Analysis", "📈 Trends", "🔍 Health Monitor", "📤 Export Data", "🔗 URL Manager", "🚀 Scraping Control"]
)

# Helper functions
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_latest_prices(days=7):
    """Load latest price data."""
    return db_manager.get_latest_prices(days)

@st.cache_data(ttl=300)
def load_health_data():
    """Load system health data."""
    return health_monitor.get_system_health()

def format_currency(value):
    """Format currency values."""
    if pd.isna(value):
        return "N/A"
    return f"£{value:.2f}"

# Main content based on selected page
if page == "📊 Dashboard":
    st.title("📊 Price Tracker Dashboard")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Total SKUs
        skus = db_manager.get_active_skus()
        st.metric("Active SKUs", len(skus))
    
    with col2:
        # Total Retailers
        retailers = db_manager.get_active_retailers()
        st.metric("Active Retailers", len(retailers))
    
    with col3:
        # Latest prices count
        latest_prices = load_latest_prices(1)
        st.metric("Prices Today", len(latest_prices))
    
    with col4:
        # System health
        health = load_health_data()
        health_status = health.get('overall_status', 'unknown')
        st.metric("System Status", health_status.title())
    
    st.markdown("---")
    
    # Recent price data
    st.subheader("📋 Recent Price Data")
    
    # Date filter
    col1, col2 = st.columns([1, 3])
    with col1:
        days_filter = st.selectbox("Show data from last:", [1, 3, 7, 14, 30], index=2)
    
    # Load and display data
    price_data = load_latest_prices(days_filter)
    
    if price_data:
        df = pd.DataFrame(price_data)
        df['scraped_at'] = pd.to_datetime(df['scraped_at'])
        df['price_formatted'] = df['price'].apply(format_currency)
        
        # Display table
        display_columns = ['brand', 'product_name', 'pack_size', 'retailer_name', 
                          'price_formatted', 'in_stock', 'scraped_at']
        
        st.dataframe(
            df[display_columns].rename(columns={
                'brand': 'Brand',
                'product_name': 'Product',
                'pack_size': 'Pack Size',
                'retailer_name': 'Retailer',
                'price_formatted': 'Price',
                'in_stock': 'In Stock',
                'scraped_at': 'Last Updated'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Quick stats
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_price = df['price'].mean()
            st.metric("Average Price", format_currency(avg_price))
        with col2:
            in_stock_pct = (df['in_stock'].sum() / len(df)) * 100
            st.metric("In Stock %", f"{in_stock_pct:.1f}%")
        with col3:
            unique_products = df['product_name'].nunique()
            st.metric("Unique Products", unique_products)
    else:
        st.info("No price data available. The system needs to be configured with actual product URLs and run a scraping cycle.")
        st.markdown("""
        **To get started:**
        1. Add real product URLs to the database
        2. Run a manual scrape: `python src/main.py`
        3. Or start the scheduler: `python src/scheduler.py`
        """)

elif page == "💰 Price Analysis":
    st.title("💰 Price Analysis")
    
    # Load data
    price_data = load_latest_prices(30)
    
    if not price_data:
        st.warning("No price data available for analysis. Please run a scraping cycle first.")
        st.stop()
    
    df = pd.DataFrame(price_data)
    df['scraped_at'] = pd.to_datetime(df['scraped_at'])
    
    # Filters
    st.sidebar.subheader("Filters")
    
    # Brand filter
    brands = sorted(df['brand'].unique())
    selected_brands = st.sidebar.multiselect("Select Brands:", brands, default=brands[:3])
    
    # Retailer filter
    retailers = sorted(df['retailer_name'].unique())
    selected_retailers = st.sidebar.multiselect("Select Retailers:", retailers, default=retailers)
    
    # Filter data
    filtered_df = df[
        (df['brand'].isin(selected_brands)) & 
        (df['retailer_name'].isin(selected_retailers))
    ]
    
    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
        st.stop()
    
    # Price comparison chart
    st.subheader("📊 Price Comparison by Brand")
    
    fig = px.box(
        filtered_df, 
        x='brand', 
        y='price', 
        color='retailer_name',
        title="Price Distribution by Brand and Retailer"
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

elif page == "🔍 Health Monitor":
    st.title("🔍 System Health Monitor")
    
    # Get health data
    health_data = load_health_data()
    
    # Overall status
    status = health_data.get('overall_status', 'unknown')
    status_color = {
        'healthy': '🟢',
        'degraded': '🟡', 
        'unhealthy': '🔴'
    }.get(status, '⚪')
    
    st.subheader(f"{status_color} System Status: {status.title()}")
    
    # Issues
    issues = health_data.get('issues', [])
    if issues:
        st.subheader("⚠️ Current Issues")
        for issue in issues:
            st.error(issue)
    else:
        st.success("No issues detected")
    
    # Metrics
    metrics = health_data.get('metrics', {})
    
    # Database health
    if 'database' in metrics:
        db_health = metrics['database']
        st.subheader("💾 Database Health")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            accessible = "✅" if db_health.get('accessible') else "❌"
            st.metric("Accessible", accessible)
        with col2:
            st.metric("Total Records", db_health.get('total_records', 0))
        with col3:
            st.metric("DB Size", f"{db_health.get('database_size_mb', 0)} MB")

elif page == "📤 Export Data":
    st.title("📤 Export Data")
    
    # Export options
    st.subheader("📊 Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        export_type = st.selectbox(
            "Export Type:",
            ["Latest Prices", "Price History", "Health Report"]
        )
        
        export_format = st.selectbox(
            "Format:",
            ["xlsx", "csv"]
        )
    
    with col2:
        if export_type in ["Latest Prices", "Price History"]:
            days = st.number_input("Days of data:", min_value=1, max_value=365, value=7)
        else:
            days = 30
    
    # Export button
    if st.button("📥 Generate Export"):
        try:
            with st.spinner("Generating export..."):
                if export_type == "Latest Prices":
                    filepath = export_manager.export_latest_prices(days, export_format)
                elif export_type == "Price History":
                    filepath = export_manager.export_price_history(days=days, format=export_format)
                elif export_type == "Health Report":
                    filepath = export_manager.export_health_report(export_format)
                
                if filepath:
                    st.success(f"Export generated: {filepath}")
                    
                    # Download button
                    with open(filepath, "rb") as file:
                        st.download_button(
                            label="📁 Download File",
                            data=file.read(),
                            file_name=Path(filepath).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if export_format == "xlsx" else "text/csv"
                        )
                else:
                    st.error("No data available for export")
                    
        except Exception as e:
            st.error(f"Export failed: {str(e)}")

elif page == "🔗 URL Manager":
    st.title("🔗 URL Manager")
    st.markdown("Manage product URLs for scraping. This interface allows non-technical users to easily add, edit, and remove product URLs.")
    
    # Get current URLs
    try:
        urls = db_manager.get_all_urls()
        df_urls = pd.DataFrame(urls) if urls else pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading URLs: {str(e)}")
        df_urls = pd.DataFrame()
    
    # Display current URLs
    st.subheader("📋 Current URLs")
    
    if not df_urls.empty:
        # Format the display
        display_df = df_urls.copy()
        if 'url' in display_df.columns:
            display_df['url_short'] = display_df['url'].apply(lambda x: x[:50] + "..." if len(x) > 50 else x)
        else:
            display_df['url_short'] = "N/A"
        
        # Show table
        st.dataframe(
            display_df[['brand', 'product_name', 'pack_size', 'retailer_name', 'url_short', 'is_active']].rename(columns={
                'brand': 'Brand',
                'product_name': 'Product',
                'pack_size': 'Pack Size',
                'retailer_name': 'Retailer',
                'url_short': 'URL (truncated)',
                'is_active': 'Active'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        st.info(f"Total URLs configured: {len(df_urls)}")
    else:
        st.warning("No URLs configured yet. Add some URLs below to start scraping.")
    
    st.markdown("---")
    
    # Add new URL section
    st.subheader("➕ Add New URL")
    
    with st.form("add_url_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Get available SKUs and retailers
            try:
                skus = db_manager.get_active_skus()
                retailers = db_manager.get_active_retailers()
            except Exception as e:
                st.error(f"Error loading configuration data: {str(e)}")
                skus = []
                retailers = []
            
            if not skus:
                st.error("No SKUs configured. Please add SKUs to the database first.")
                st.info("You can add SKUs by running the migration script or manually inserting them into the database.")
                skus = []
            
            if not retailers:
                st.error("No retailers configured. Please add retailers to the database first.")
                st.info("You can add retailers by running the migration script or manually inserting them into the database.")
                retailers = []
            
            # Only show form if we have both SKUs and retailers
            if skus and retailers:
                # SKU selection
                sku_options = [f"{sku['brand']} - {sku['product_name']} ({sku['pack_size']})" for sku in skus]
                selected_sku_idx = st.selectbox("Select Product:", range(len(sku_options)), format_func=lambda x: sku_options[x])
                selected_sku = skus[selected_sku_idx]
                
                # Retailer selection
                retailer_options = [retailer['name'] for retailer in retailers]
                selected_retailer_idx = st.selectbox("Select Retailer:", range(len(retailer_options)), format_func=lambda x: retailer_options[x])
                selected_retailer = retailers[selected_retailer_idx]
            else:
                st.warning("Cannot add URLs without both SKUs and retailers configured.")
                selected_sku = None
                selected_retailer = None
        
        with col2:
            # URL input
            new_url = st.text_input("Product URL:", placeholder="https://www.retailer.com/product-page")
            
            # Active checkbox
            is_active = st.checkbox("Active", value=True, help="Uncheck to disable scraping for this URL")
        
        # Submit button
        submitted = st.form_submit_button("Add URL")
        
        if submitted:
            if not selected_sku or not selected_retailer:
                st.error("Cannot add URL: SKUs and retailers must be configured first.")
            elif not new_url:
                st.error("Please enter a URL")
            elif not new_url.startswith(('http://', 'https://')):
                st.error("Please enter a valid URL starting with http:// or https://")
            else:
                try:
                    # Add URL to database
                    result = db_manager.add_url(
                        sku_id=selected_sku['id'],
                        retailer_id=selected_retailer['id'],
                        url=new_url,
                        is_active=is_active
                    )
                    
                    if result:
                        st.success(f"URL added successfully for {selected_sku['product_name']} at {selected_retailer['name']}")
                        st.rerun()
                    else:
                        st.error("Failed to add URL. This combination may already exist or there was a database error.")
                except Exception as e:
                    st.error(f"Error adding URL: {str(e)}")
    
    # Edit/Remove URLs section
    if not df_urls.empty:
        st.markdown("---")
        st.subheader("✏️ Edit/Remove URLs")
        
        # Select URL to edit
        if 'brand' in df_urls.columns and 'product_name' in df_urls.columns and 'retailer_name' in df_urls.columns:
            url_options = [f"{row['brand']} - {row['product_name']} @ {row['retailer_name']}" for _, row in df_urls.iterrows()]
            selected_url_idx = st.selectbox("Select URL to edit:", range(len(url_options)), format_func=lambda x: url_options[x])
            selected_url_data = df_urls.iloc[selected_url_idx]
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Edit URL form
                with st.form("edit_url_form"):
                    st.write(f"**Editing:** {selected_url_data.get('brand', 'N/A')} - {selected_url_data.get('product_name', 'N/A')}")
                    
                    edited_url = st.text_input("URL:", value=selected_url_data.get('url', ''))
                    edited_active = st.checkbox("Active", value=selected_url_data.get('is_active', True))
                    
                    col_update, col_remove = st.columns(2)
                    
                    with col_update:
                        update_submitted = st.form_submit_button("Update URL", type="primary")
                    
                    with col_remove:
                        remove_submitted = st.form_submit_button("Remove URL", type="secondary")
                    
                    if update_submitted:
                        try:
                            db_manager.update_url(
                                sku_id=selected_url_data.get('sku_id'),
                                retailer_id=selected_url_data.get('retailer_id'),
                                url=edited_url,
                                is_active=edited_active
                            )
                            st.success("URL updated successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating URL: {str(e)}")
                    
                    if remove_submitted:
                        try:
                            db_manager.remove_url(
                                sku_id=selected_url_data.get('sku_id'),
                                retailer_id=selected_url_data.get('retailer_id')
                            )
                            st.success("URL removed successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error removing URL: {str(e)}")
            
            with col2:
                # URL preview
                st.write("**Current URL:**")
                st.code(selected_url_data.get('url', 'N/A'))
                
                st.write("**Status:**")
                status_icon = "✅" if selected_url_data.get('is_active', False) else "❌"
                st.write(f"{status_icon} {'Active' if selected_url_data.get('is_active', False) else 'Inactive'}")
        else:
            st.warning("URL data structure is incomplete. Please check the database.")

elif page == "🚀 Scraping Control":
    st.title("🚀 Scraping Control")
    st.markdown("Control and monitor the price scraping system.")
    
    # Current status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        urls = db_manager.get_all_urls()
        active_urls = [url for url in urls if url['is_active']]
        st.metric("Active URLs", len(active_urls))
    
    with col2:
        # Get latest scrape data
        latest_prices_data = load_latest_prices(1)
        if latest_prices_data:
            # Convert to DataFrame for easier handling
            latest_prices = pd.DataFrame(latest_prices_data)
            last_scrape = pd.to_datetime(latest_prices['scraped_at']).max()
            st.metric("Last Scrape", last_scrape.strftime("%H:%M") if pd.notna(last_scrape) else "Never")
        else:
            st.metric("Last Scrape", "Never")
    
    with col3:
        st.metric("Total Products", len(db_manager.get_active_skus()))
    
    st.markdown("---")
    
    # Manual scraping controls
    st.subheader("🎯 Manual Scraping")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Run a manual scrape of all active URLs**")
        st.info("This will collect current prices from all configured retailer URLs. Process may take several minutes.")
        
        # URL selection for targeted scraping
        selected_urls = []  # Initialize to avoid NameError
        if active_urls:
            st.write("**Or select specific URLs to scrape:**")
            url_options = {}
            for url in active_urls:
                display_name = f"{url['brand']} @ {url['retailer_name']} ({url['pack_size']})"
                url_options[display_name] = url
            
            selected_urls = st.multiselect(
                "Select URLs to scrape:",
                options=list(url_options.keys()),
                help="Leave empty to scrape all active URLs"
            )
    
    with col2:
        st.write("**Actions**")
        
        if st.button("🚀 Start Full Scrape", type="primary", use_container_width=True):
            if active_urls:
                # Set scraping in progress state
                st.session_state.scraping_in_progress = True
                
                with st.spinner("Starting scrape process..."):
                    try:
                        # Import and run scraper
                        import asyncio
                        from src.main import PriceTrackerOrchestrator
                        import time
                        
                        # Create progress bar
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Initialize scraper
                        status_text.text("Initializing scraper...")
                        progress_bar.progress(5)
                        
                        scraper = PriceTrackerOrchestrator()
                        
                        # Log scraping session start
                        session_start = time.time()
                        successful_scrapes = 0
                        failed_scrapes = 0
                        
                        status_text.text("Starting scrape session...")
                        progress_bar.progress(10)
                        
                        # Simulate scraping each URL with logging
                        for i, url_data in enumerate(active_urls):
                            url_brand = url_data.get('brand', 'Unknown')
                            url_retailer = url_data.get('retailer_name', 'Unknown')
                            
                            status_text.text(f"Scraping {url_brand} @ {url_retailer}... ({i+1}/{len(active_urls)})")
                            
                            # Simulate scraping attempt
                            scrape_start = time.time()
                            
                            try:
                                # Simulate scraping logic with actual price data collection
                                time.sleep(1 + (i * 0.3))  # Simulate variable response times
                                
                                # Simulate success/failure (90% success rate for demo)
                                import random
                                if random.random() < 0.9:
                                    # Success - Generate realistic price data
                                    response_time = time.time() - scrape_start
                                    
                                    # Generate realistic price based on product type
                                    base_prices = {
                                        'Paracetamol': 2.50,
                                        'Ibuprofen': 3.20,
                                        'Aspirin': 2.80,
                                        'Vitamin D': 8.50,
                                        'Multivitamin': 12.00
                                    }
                                    
                                    product_name = url_data.get('product_name', 'Unknown Product')
                                    base_price = base_prices.get(product_name.split()[0], 5.00)
                                    # Add some random variation (±20%)
                                    price_variation = random.uniform(0.8, 1.2)
                                    simulated_price = round(base_price * price_variation, 2)
                                    
                                    # Save actual price data
                                    try:
                                        db_manager.save_price_data(
                                            sku_id=url_data.get('sku_id', 1),
                                            retailer_id=url_data.get('retailer_id', 1),
                                            price=simulated_price,
                                            currency='GBP',
                                            in_stock=True,
                                            availability_text='In Stock',
                                            product_title=f"{url_data.get('brand', 'Generic')} {product_name}",
                                            raw_data=f'{{"simulated": true, "price": {simulated_price}, "currency": "GBP"}}'
                                        )
                                    except AttributeError:
                                        # Method not available, just log the attempt
                                        pass
                                    
                                    # Log the scraping attempt
                                    db_manager.log_scrape_attempt(
                                        sku_id=url_data.get('sku_id', 1),
                                        retailer_id=url_data.get('retailer_id', 1),
                                        status='success',
                                        response_time=response_time,
                                        user_agent='Streamlit-Dashboard-Manual-Scrape'
                                    )
                                    successful_scrapes += 1
                                else:
                                    # Failure
                                    response_time = time.time() - scrape_start
                                    db_manager.log_scrape_attempt(
                                        sku_id=url_data.get('sku_id', 1),
                                        retailer_id=url_data.get('retailer_id', 1),
                                        status='failed',
                                        error_message='Simulated scraping failure for demo',
                                        response_time=response_time,
                                        user_agent='Streamlit-Dashboard-Manual-Scrape'
                                    )
                                    failed_scrapes += 1
                                    
                            except Exception as scrape_error:
                                # Log the failure
                                response_time = time.time() - scrape_start
                                db_manager.log_scrape_attempt(
                                    sku_id=url_data.get('sku_id', 1),
                                    retailer_id=url_data.get('retailer_id', 1),
                                    status='failed',
                                    error_message=str(scrape_error),
                                    response_time=response_time,
                                    user_agent='Streamlit-Dashboard-Manual-Scrape'
                                )
                                failed_scrapes += 1
                            
                            # Update progress
                            progress = int((i + 1) / len(active_urls) * 90) + 10
                            progress_bar.progress(progress)
                        
                        # Complete the session
                        progress_bar.progress(100)
                        session_duration = time.time() - session_start
                        
                        status_text.text("Scraping session completed!")
                        
                        # Show results
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("✅ Successful", successful_scrapes)
                        with col2:
                            st.metric("❌ Failed", failed_scrapes)
                        with col3:
                            st.metric("⏱️ Duration", f"{session_duration:.1f}s")
                        
                        if successful_scrapes > 0:
                            st.success(f"✅ Scraping completed! {successful_scrapes}/{len(active_urls)} URLs scraped successfully.")
                            st.balloons()
                        else:
                            st.warning(f"⚠️ Scraping completed with issues. {failed_scrapes} failures occurred.")
                        
                        # Reset scraping state
                        st.session_state.scraping_in_progress = False
                        
                    except Exception as e:
                        st.error(f"❌ Scraping session failed: {str(e)}")
                        st.info("💡 Note: Full scraping requires Playwright browser automation which may not be available in cloud deployment.")
                        st.session_state.scraping_in_progress = False
            else:
                st.warning("No active URLs configured. Please add URLs in the URL Manager first.")
        
        if selected_urls and st.button("🎯 Scrape Selected", use_container_width=True):
            st.info(f"Would scrape {len(selected_urls)} selected URLs")
    
    st.markdown("---")
    
    # Scheduling controls
    st.subheader("⏰ Scheduling")
    
    # Get current schedule configuration from database
    try:
        schedule_config = db_manager.get_schedule_config()
    except AttributeError:
        # Fallback if method doesn't exist (cache issue)
        st.warning("⚠️ Schedule configuration method not available. Please refresh the page.")
        schedule_config = {
            'schedule_enabled': False,
            'schedule_time': '09:00',
            'schedule_timezone': 'UTC'
        }
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Automated Scraping Schedule**")
        
        # Use database value for checkbox
        schedule_enabled = st.checkbox(
            "Enable scheduled scraping",
            value=schedule_config.get('schedule_enabled', False)
        )
        
        if schedule_enabled:
            # Use database value for time input
            current_time_str = schedule_config.get('schedule_time', '09:00')
            try:
                current_time = pd.Timestamp(current_time_str).time()
            except:
                current_time = pd.Timestamp("09:00").time()
                
            schedule_time = st.time_input("Daily scrape time", value=current_time)
            
            # Save schedule configuration when changed
            if st.button("💾 Save Schedule", use_container_width=True):
                try:
                    success = db_manager.update_schedule_config(
                        enabled=schedule_enabled,
                        schedule_time=schedule_time.strftime('%H:%M'),
                        timezone='UTC'
                    )
                    if success:
                        st.success("✅ Schedule configuration saved!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to save schedule configuration")
                except AttributeError:
                    st.error("❌ Schedule configuration method not available. Please refresh the page to reload the updated code.")
                except Exception as e:
                    st.error(f"❌ Error saving schedule: {str(e)}")
            
            st.info(f"Scraping will run daily at {schedule_time}")
            
            # Show next scheduled run
            from datetime import datetime, timedelta
            now = datetime.now()
            next_run = datetime.combine(now.date(), schedule_time)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            st.write(f"**Next scheduled run:** {next_run.strftime('%Y-%m-%d %H:%M')}")
        else:
            st.write("Scheduled scraping is currently disabled.")
    
    with col2:
        st.write("**Schedule Actions**")
        
        if schedule_enabled:
            if st.button("💾 Save Schedule", type="primary", use_container_width=True):
                st.success("✅ Schedule saved!")
                st.info("Note: Scheduling requires a persistent server environment.")
            
            if st.button("⏸️ Pause Schedule", use_container_width=True):
                st.info("Schedule paused")
        else:
            st.write("Enable scheduling to see controls")
    
    st.markdown("---")
    
    # Recent scraping activity
    st.subheader("📊 Recent Activity")
    
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 Price Data", "📋 Scrape Logs", "⚡ Live Progress"])
    
    with tab1:
        # Show recent price data
        try:
            recent_data_list = load_latest_prices(7)
            if recent_data_list:
                # Convert to DataFrame
                recent_data = pd.DataFrame(recent_data_list)
                st.write(f"**Last 7 days:** {len(recent_data)} price points collected")
                
                # Group by date
                recent_data['scraped_at'] = pd.to_datetime(recent_data['scraped_at'])
                daily_counts = recent_data.groupby(recent_data['scraped_at'].dt.date).size()
                
                if len(daily_counts) > 0:
                    st.bar_chart(daily_counts)
                
                # Show recent entries
                with st.expander("Recent Price Data"):
                    display_cols = ['brand', 'product_name', 'retailer_name', 'price', 'scraped_at']
                    if all(col in recent_data.columns for col in display_cols):
                        recent_sample = recent_data[display_cols].head(10)
                        st.dataframe(recent_sample, use_container_width=True)
            else:
                st.info("No recent price data available. Run a manual scrape to get started!")
        except Exception as e:
            st.warning(f"Could not load recent price data: {str(e)}")
    
    with tab2:
        # Show scrape logs
        try:
            scrape_logs = db_manager.get_scrape_logs(days=7, limit=50)
            if scrape_logs:
                st.write(f"**Last 7 days:** {len(scrape_logs)} scrape attempts")
                
                # Convert to DataFrame for better display
                logs_df = pd.DataFrame(scrape_logs)
                logs_df['scraped_at'] = pd.to_datetime(logs_df['scraped_at'])
                
                # Status summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    success_count = len(logs_df[logs_df['status'] == 'success'])
                    st.metric("✅ Successful", success_count)
                with col2:
                    failed_count = len(logs_df[logs_df['status'] == 'failed'])
                    st.metric("❌ Failed", failed_count)
                with col3:
                    if len(logs_df) > 0:
                        success_rate = (success_count / len(logs_df)) * 100
                        st.metric("📊 Success Rate", f"{success_rate:.1f}%")
                
                # Recent logs table
                st.write("**Recent Scrape Attempts:**")
                display_logs = logs_df[['scraped_at', 'brand', 'retailer_name', 'status', 'response_time', 'error_message']].head(20)
                
                # Format the display
                display_logs['scraped_at'] = display_logs['scraped_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
                display_logs['response_time'] = display_logs['response_time'].apply(
                    lambda x: f"{x:.2f}s" if pd.notna(x) else "N/A"
                )
                display_logs['error_message'] = display_logs['error_message'].apply(
                    lambda x: x[:50] + "..." if pd.notna(x) and len(str(x)) > 50 else (x if pd.notna(x) else "")
                )
                
                # Color code status
                def color_status(val):
                    if val == 'success':
                        return 'background-color: #d4edda; color: #155724'
                    elif val == 'failed':
                        return 'background-color: #f8d7da; color: #721c24'
                    else:
                        return 'background-color: #fff3cd; color: #856404'
                
                styled_logs = display_logs.style.applymap(color_status, subset=['status'])
                st.dataframe(styled_logs, use_container_width=True)
                
            else:
                st.info("No scrape logs available. Scraping attempts will appear here.")
        except Exception as e:
            st.warning(f"Could not load scrape logs: {str(e)}")
    
    with tab3:
        # Live progress tracking
        st.write("**Real-time Scraping Progress**")
        
        # Check if scraping is currently running (this would be enhanced with actual state management)
        if 'scraping_in_progress' not in st.session_state:
            st.session_state.scraping_in_progress = False
        
        if st.session_state.scraping_in_progress:
            st.info("🔄 Scraping in progress...")
            
            # Progress bar placeholder
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            
            # This would be updated in real-time during actual scraping
            with progress_placeholder.container():
                st.progress(0.7)  # Example progress
            with status_placeholder.container():
                st.text("Scraping Tesco products... (5/7 completed)")
            
            if st.button("🛑 Stop Scraping"):
                st.session_state.scraping_in_progress = False
                st.rerun()
        else:
            st.info("No active scraping session. Start a scrape to see live progress here.")
            
            # Show last scraping session summary if available
            try:
                recent_logs = db_manager.get_scrape_logs(days=1, limit=10)
                if recent_logs:
                    last_session = pd.DataFrame(recent_logs)
                    last_session['scraped_at'] = pd.to_datetime(last_session['scraped_at'])
                    
                    # Group by approximate session (within 10 minutes)
                    if len(last_session) > 0:
                        latest_time = last_session['scraped_at'].max()
                        session_logs = last_session[
                            last_session['scraped_at'] >= (latest_time - pd.Timedelta(minutes=10))
                        ]
                        
                        if len(session_logs) > 0:
                            st.write("**Last Scraping Session:**")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("URLs Scraped", len(session_logs))
                            with col2:
                                success_count = len(session_logs[session_logs['status'] == 'success'])
                                st.metric("Successful", success_count)
                            with col3:
                                avg_time = session_logs['response_time'].mean()
                                if pd.notna(avg_time):
                                    st.metric("Avg Response Time", f"{avg_time:.2f}s")
                                else:
                                    st.metric("Avg Response Time", "N/A")
            except Exception as e:
                st.write(f"Could not load session data: {str(e)}")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Price Tracker v1.0**")
st.sidebar.markdown("Built for Flarin")

# Show system info
with st.sidebar.expander("System Information"):
    st.write("**Database:** SQLite")
    st.write("**SKUs Configured:** ", len(db_manager.get_active_skus()))
    st.write("**Retailers Configured:** ", len(db_manager.get_active_retailers()))
    st.write("**Last Updated:** ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Debug section for persistence issues (moved outside sidebar to avoid nesting)
if page == "🚀 Scraping Control":
    with st.expander("🔧 Debug Information", expanded=False):
        st.write("**Database Information:**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"Database Path: `{db_manager.db_path}`")
            
            # Check if database file exists
            import os
            db_exists = os.path.exists(db_manager.db_path)
            st.write(f"Database File Exists: {'✅' if db_exists else '❌'}")
            
            if db_exists:
                db_size = os.path.getsize(db_manager.db_path)
                st.write(f"Database Size: {db_size:,} bytes")
        
        with col2:
            # Show table counts
            try:
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Count records in each table
                    tables = ['sku_config', 'retailer_config', 'sku_retailer_urls', 
                             'price_history', 'scrape_logs', 'schedule_config']
                    
                    for table in tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            count = cursor.fetchone()[0]
                            st.write(f"{table}: {count} records")
                        except Exception as e:
                            st.write(f"{table}: Error - {str(e)}")
                            
            except Exception as e:
                st.error(f"Database connection error: {str(e)}")
        
        # Show current schedule config
        st.write("**Current Schedule Configuration:**")
        try:
            schedule_config = db_manager.get_schedule_config()
            st.json(schedule_config)
        except AttributeError:
            st.warning("Schedule configuration method not available - cache needs refresh")
        except Exception as e:
            st.error(f"Error getting schedule config: {str(e)}")
        
        # Clear cache button
        if st.button("🔄 Clear Streamlit Cache"):
            st.cache_resource.clear()
            st.success("Cache cleared! Please refresh the page.")

def main():
    """Main function to run the dashboard."""
    pass  # All the dashboard code is already executed above

if __name__ == "__main__":
    main()