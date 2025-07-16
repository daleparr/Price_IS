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

# Page configuration
st.set_page_config(
    page_title="Price Tracker Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize components
@st.cache_resource
def init_components():
    """Initialize database and utility components."""
    db_manager = DatabaseManager()
    
    # Initialize database with tables and data for cloud deployment
    try:
        # Create tables if they don't exist
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
    ["📊 Dashboard", "💰 Price Analysis", "📈 Trends", "🔍 Health Monitor", "📤 Export Data", "🔗 URL Manager"]
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