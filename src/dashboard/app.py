"""
Streamlit dashboard for the price tracker system.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import asyncio
from pathlib import Path
import sys

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.models import DatabaseManager
from src.utils.export_manager import ExportManager
from src.utils.health_monitor import HealthMonitor
from src.utils.data_validator import DataQualityChecker
from src.scheduler import PriceTrackerScheduler

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
    settings = {
        'export_path': 'exports/',
        'log_level': 'INFO',
        'log_file': 'logs/dashboard.log'
    }
    export_manager = ExportManager(db_manager, settings)
    health_monitor = HealthMonitor(db_manager, settings)
    quality_checker = DataQualityChecker(db_manager)
    scheduler = PriceTrackerScheduler()
    
    return db_manager, export_manager, health_monitor, quality_checker, scheduler

db_manager, export_manager, health_monitor, quality_checker, scheduler = init_components()

# Sidebar
st.sidebar.title("🏥 Price Tracker")
st.sidebar.markdown("---")

# Navigation
page = st.sidebar.selectbox(
    "Navigate to:",
    ["📊 Dashboard", "💰 Price Analysis", "📈 Trends", "🔍 Health Monitor", "📤 Export Data", "⚙️ System Control"]
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
        health_color = {
            'healthy': 'normal',
            'degraded': 'inverse',
            'unhealthy': 'off'
        }.get(health_status, 'off')
        st.metric("System Status", health_status.title(), delta_color=health_color)
    
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
        st.info("No price data available for the selected period.")

elif page == "💰 Price Analysis":
    st.title("💰 Price Analysis")
    
    # Load data
    price_data = load_latest_prices(30)
    
    if not price_data:
        st.warning("No price data available for analysis.")
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
    
    # Price comparison table
    st.subheader("📋 Price Comparison Table")
    
    # Create pivot table
    pivot_df = filtered_df.pivot_table(
        index=['brand', 'product_name', 'pack_size'],
        columns='retailer_name',
        values='price',
        aggfunc='mean'
    ).round(2)
    
    # Add statistics
    pivot_df['Min Price'] = pivot_df.min(axis=1)
    pivot_df['Max Price'] = pivot_df.max(axis=1)
    pivot_df['Price Range'] = (pivot_df['Max Price'] - pivot_df['Min Price']).round(2)
    
    st.dataframe(pivot_df, use_container_width=True)
    
    # Cheapest/Most expensive
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💚 Cheapest Options")
        cheapest = filtered_df.loc[filtered_df.groupby(['brand', 'product_name'])['price'].idxmin()]
        cheapest_display = cheapest[['brand', 'product_name', 'retailer_name', 'price']].copy()
        cheapest_display['price'] = cheapest_display['price'].apply(format_currency)
        st.dataframe(cheapest_display, hide_index=True)
    
    with col2:
        st.subheader("💸 Most Expensive Options")
        expensive = filtered_df.loc[filtered_df.groupby(['brand', 'product_name'])['price'].idxmax()]
        expensive_display = expensive[['brand', 'product_name', 'retailer_name', 'price']].copy()
        expensive_display['price'] = expensive_display['price'].apply(format_currency)
        st.dataframe(expensive_display, hide_index=True)

elif page == "📈 Trends":
    st.title("📈 Price Trends")
    
    # Load historical data
    with db_manager.get_connection() as conn:
        query = """
            SELECT 
                ph.*,
                sc.brand,
                sc.product_name,
                sc.pack_size,
                rc.name as retailer_name
            FROM price_history ph
            JOIN sku_config sc ON ph.sku_id = sc.id
            JOIN retailer_config rc ON ph.retailer_id = rc.id
            WHERE ph.scraped_at >= datetime('now', '-90 days')
            AND ph.price IS NOT NULL
            ORDER BY ph.scraped_at
        """
        df = pd.read_sql_query(query, conn)
    
    if df.empty:
        st.warning("No historical data available for trend analysis.")
        st.stop()
    
    df['scraped_at'] = pd.to_datetime(df['scraped_at'])
    df['date'] = df['scraped_at'].dt.date
    
    # Product selector
    products = df.groupby(['brand', 'product_name']).size().reset_index()
    products['display_name'] = products['brand'] + ' - ' + products['product_name']
    
    selected_product = st.selectbox(
        "Select Product for Trend Analysis:",
        products['display_name'].tolist()
    )
    
    if selected_product:
        brand, product_name = selected_product.split(' - ', 1)
        product_df = df[(df['brand'] == brand) & (df['product_name'] == product_name)]
        
        # Daily average prices
        daily_prices = product_df.groupby(['date', 'retailer_name'])['price'].mean().reset_index()
        
        # Line chart
        fig = px.line(
            daily_prices,
            x='date',
            y='price',
            color='retailer_name',
            title=f"Price Trend: {selected_product}",
            labels={'price': 'Price (£)', 'date': 'Date'}
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            current_avg = product_df[product_df['date'] == product_df['date'].max()]['price'].mean()
            st.metric("Current Avg Price", format_currency(current_avg))
        
        with col2:
            price_change = product_df['price'].pct_change().mean() * 100
            st.metric("Avg Daily Change", f"{price_change:.2f}%")
        
        with col3:
            volatility = product_df['price'].std()
            st.metric("Price Volatility", format_currency(volatility))

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
    
    # Scrape health
    if 'scrape_health' in metrics:
        scrape_health = metrics['scrape_health']
        st.subheader("🔄 Scraping Health")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Success Rate", f"{scrape_health.get('success_rate', 0)}%")
        with col2:
            st.metric("Total Attempts", scrape_health.get('total_attempts', 0))
        with col3:
            st.metric("Successful", scrape_health.get('successful_attempts', 0))
        with col4:
            st.metric("Avg Response Time", f"{scrape_health.get('average_response_time', 0):.2f}s")
    
    # Data freshness
    if 'data_freshness' in metrics:
        freshness = metrics['data_freshness']
        st.subheader("📅 Data Freshness")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fresh Data", f"{freshness.get('fresh_data_count', 0)}/{freshness.get('total_sku_retailer_pairs', 0)}")
        with col2:
            st.metric("Stale Percentage", f"{freshness.get('stale_percentage', 0)}%")
        with col3:
            st.metric("Oldest Data", f"{freshness.get('oldest_data_age_hours', 0):.1f}h")
    
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
    
    # Refresh button
    if st.button("🔄 Refresh Health Data"):
        st.cache_data.clear()
        st.rerun()

elif page == "📤 Export Data":
    st.title("📤 Export Data")
    
    # Export options
    st.subheader("📊 Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        export_type = st.selectbox(
            "Export Type:",
            ["Latest Prices", "Price History", "Price Comparison", "Health Report", "Power BI Dataset"]
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
                elif export_type == "Price Comparison":
                    filepath = export_manager.export_price_comparison(days, export_format)
                elif export_type == "Health Report":
                    filepath = export_manager.export_health_report(export_format)
                elif export_type == "Power BI Dataset":
                    filepath = export_manager.export_power_bi_dataset()
                
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
    
    # Export history
    st.subheader("📁 Export History")
    export_history = export_manager.get_export_history()
    
    if export_history:
        history_df = pd.DataFrame(export_history)
        history_df['created_at'] = pd.to_datetime(history_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            history_df[['filename', 'size_mb', 'created_at']].rename(columns={
                'filename': 'File Name',
                'size_mb': 'Size (MB)',
                'created_at': 'Created'
            }),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No export history available")

elif page == "⚙️ System Control":
    st.title("⚙️ System Control")
    
    # Scheduler status
    st.subheader("📅 Scheduler Status")
    
    try:
        scheduler_status = scheduler.get_scheduler_status()
        
        col1, col2 = st.columns(2)
        with col1:
            status_icon = "🟢" if scheduler_status['is_running'] else "🔴"
            st.metric("Scheduler", f"{status_icon} {'Running' if scheduler_status['is_running'] else 'Stopped'}")
        
        with col2:
            st.metric("Scheduled Jobs", scheduler_status['scheduled_jobs'])
        
        # Last run times
        if scheduler_status['last_scrape_time']:
            st.info(f"Last scrape: {scheduler_status['last_scrape_time']}")
        
        if scheduler_status['last_health_check_time']:
            st.info(f"Last health check: {scheduler_status['last_health_check_time']}")
        
    except Exception as e:
        st.error(f"Could not get scheduler status: {str(e)}")
    
    # Manual controls
    st.subheader("🎮 Manual Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Run Manual Scrape"):
            try:
                with st.spinner("Running scrape..."):
                    summary = scheduler.run_manual_scrape()
                st.success(f"Scrape completed! Success rate: {summary.get('success_rate', 0)}%")
                st.json(summary)
            except Exception as e:
                st.error(f"Scrape failed: {str(e)}")
    
    with col2:
        if st.button("🏥 Run Health Check"):
            try:
                with st.spinner("Running health check..."):
                    health = health_monitor.get_system_health()
                st.success("Health check completed!")
                st.json(health)
            except Exception as e:
                st.error(f"Health check failed: {str(e)}")
    
    with col3:
        if st.button("🔍 Run Quality Check"):
            try:
                with st.spinner("Running quality check..."):
                    quality = quality_checker.generate_quality_report()
                st.success("Quality check completed!")
                st.json(quality)
            except Exception as e:
                st.error(f"Quality check failed: {str(e)}")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Price Tracker v1.0**")
st.sidebar.markdown("Built for Flarin")