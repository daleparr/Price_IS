"""
URL Management interface for the price tracker system.
This provides a user-friendly way to manage product URLs without technical knowledge.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.models import DatabaseManager

# Page configuration
st.set_page_config(
    page_title="URL Manager - Price Tracker",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
@st.cache_resource
def init_db():
    return DatabaseManager()

db_manager = init_db()

st.title("🔗 Product URL Manager")
st.markdown("Manage product URLs for price tracking without technical knowledge")

# Sidebar
st.sidebar.title("🔗 URL Manager")
st.sidebar.markdown("---")

# Navigation
section = st.sidebar.selectbox(
    "Select Section:",
    ["📋 View Current URLs", "➕ Add New URL", "✏️ Edit URLs", "🗑️ Remove URLs"]
)

def load_url_data():
    """Load current URL mappings with product and retailer details."""
    with db_manager.get_connection() as conn:
        query = """
            SELECT 
                sru.id,
                sru.sku_id,
                sru.retailer_id,
                sru.product_url,
                sru.active,
                sc.brand,
                sc.product_name,
                sc.pack_size,
                rc.name as retailer_name
            FROM sku_retailer_urls sru
            JOIN sku_config sc ON sru.sku_id = sc.id
            JOIN retailer_config rc ON sru.retailer_id = rc.id
            ORDER BY sc.brand, sc.product_name, rc.name
        """
        return pd.read_sql_query(query, conn)

def get_available_skus():
    """Get list of available SKUs."""
    skus = db_manager.get_active_skus()
    return {f"{sku['brand']} - {sku['product_name']} ({sku['pack_size']})": sku['id'] for sku in skus}

def get_available_retailers():
    """Get list of available retailers."""
    retailers = db_manager.get_active_retailers()
    return {retailer['name']: retailer['id'] for retailer in retailers}

if section == "📋 View Current URLs":
    st.subheader("📋 Current Product URLs")
    
    # Load current URLs
    url_data = load_url_data()
    
    if not url_data.empty:
        # Display summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total URLs", len(url_data))
        with col2:
            active_urls = len(url_data[url_data['active'] == 1])
            st.metric("Active URLs", active_urls)
        with col3:
            unique_products = url_data['sku_id'].nunique()
            st.metric("Products Covered", unique_products)
        
        st.markdown("---")
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            brand_filter = st.selectbox(
                "Filter by Brand:",
                ["All"] + sorted(url_data['brand'].unique().tolist())
            )
        with col2:
            retailer_filter = st.selectbox(
                "Filter by Retailer:",
                ["All"] + sorted(url_data['retailer_name'].unique().tolist())
            )
        
        # Apply filters
        filtered_data = url_data.copy()
        if brand_filter != "All":
            filtered_data = filtered_data[filtered_data['brand'] == brand_filter]
        if retailer_filter != "All":
            filtered_data = filtered_data[filtered_data['retailer_name'] == retailer_filter]
        
        # Display table
        display_columns = ['brand', 'product_name', 'pack_size', 'retailer_name', 'product_url', 'active']
        
        st.dataframe(
            filtered_data[display_columns].rename(columns={
                'brand': 'Brand',
                'product_name': 'Product',
                'pack_size': 'Pack Size',
                'retailer_name': 'Retailer',
                'product_url': 'Product URL',
                'active': 'Active'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # URL validation status
        st.subheader("🔍 URL Status Check")
        
        # Check for missing URLs
        missing_urls = []
        skus = db_manager.get_active_skus()
        retailers = db_manager.get_active_retailers()
        
        for sku in skus:
            for retailer in retailers:
                existing = url_data[
                    (url_data['sku_id'] == sku['id']) & 
                    (url_data['retailer_id'] == retailer['id'])
                ]
                if existing.empty:
                    missing_urls.append({
                        'brand': sku['brand'],
                        'product_name': sku['product_name'],
                        'pack_size': sku['pack_size'],
                        'retailer_name': retailer['name']
                    })
        
        if missing_urls:
            st.warning(f"⚠️ {len(missing_urls)} product-retailer combinations are missing URLs")
            with st.expander("View Missing URLs"):
                missing_df = pd.DataFrame(missing_urls)
                st.dataframe(missing_df, hide_index=True)
        else:
            st.success("✅ All product-retailer combinations have URLs configured")
            
    else:
        st.info("No URLs configured yet. Use the 'Add New URL' section to get started.")

elif section == "➕ Add New URL":
    st.subheader("➕ Add New Product URL")
    
    # Get available options
    available_skus = get_available_skus()
    available_retailers = get_available_retailers()
    
    with st.form("add_url_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            selected_sku_name = st.selectbox(
                "Select Product:",
                list(available_skus.keys())
            )
            selected_sku_id = available_skus[selected_sku_name]
            
        with col2:
            selected_retailer_name = st.selectbox(
                "Select Retailer:",
                list(available_retailers.keys())
            )
            selected_retailer_id = available_retailers[selected_retailer_name]
        
        product_url = st.text_input(
            "Product URL:",
            placeholder="https://www.retailer.com/product-page-url",
            help="Enter the full URL to the product page on the retailer's website"
        )
        
        active = st.checkbox("Active", value=True, help="Whether this URL should be used for scraping")
        
        submitted = st.form_submit_button("Add URL")
        
        if submitted:
            if not product_url:
                st.error("Please enter a product URL")
            elif not product_url.startswith(('http://', 'https://')):
                st.error("Please enter a valid URL starting with http:// or https://")
            else:
                try:
                    # Check if URL already exists
                    with db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT id FROM sku_retailer_urls 
                            WHERE sku_id = ? AND retailer_id = ?
                        """, (selected_sku_id, selected_retailer_id))
                        existing = cursor.fetchone()
                        
                        if existing:
                            st.error("A URL already exists for this product-retailer combination. Use 'Edit URLs' to modify it.")
                        else:
                            # Insert new URL
                            cursor.execute("""
                                INSERT INTO sku_retailer_urls (sku_id, retailer_id, product_url, active)
                                VALUES (?, ?, ?, ?)
                            """, (selected_sku_id, selected_retailer_id, product_url, active))
                            conn.commit()
                            
                            st.success(f"✅ Successfully added URL for {selected_sku_name} at {selected_retailer_name}")
                            st.rerun()
                            
                except Exception as e:
                    st.error(f"Error adding URL: {str(e)}")

elif section == "✏️ Edit URLs":
    st.subheader("✏️ Edit Existing URLs")
    
    # Load current URLs
    url_data = load_url_data()
    
    if not url_data.empty:
        # Select URL to edit
        url_options = {}
        for _, row in url_data.iterrows():
            display_name = f"{row['brand']} - {row['product_name']} ({row['pack_size']}) @ {row['retailer_name']}"
            url_options[display_name] = row['id']
        
        selected_url_name = st.selectbox(
            "Select URL to Edit:",
            list(url_options.keys())
        )
        selected_url_id = url_options[selected_url_name]
        
        # Get current URL data
        current_url = url_data[url_data['id'] == selected_url_id].iloc[0]
        
        with st.form("edit_url_form"):
            st.info(f"Editing: {current_url['brand']} - {current_url['product_name']} @ {current_url['retailer_name']}")
            
            new_url = st.text_input(
                "Product URL:",
                value=current_url['product_url'],
                help="Update the URL for this product-retailer combination"
            )
            
            new_active = st.checkbox(
                "Active", 
                value=bool(current_url['active']),
                help="Whether this URL should be used for scraping"
            )
            
            submitted = st.form_submit_button("Update URL")
            
            if submitted:
                if not new_url:
                    st.error("Please enter a product URL")
                elif not new_url.startswith(('http://', 'https://')):
                    st.error("Please enter a valid URL starting with http:// or https://")
                else:
                    try:
                        with db_manager.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE sku_retailer_urls 
                                SET product_url = ?, active = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (new_url, new_active, selected_url_id))
                            conn.commit()
                            
                            st.success("✅ URL updated successfully!")
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error updating URL: {str(e)}")
    else:
        st.info("No URLs to edit. Add some URLs first using the 'Add New URL' section.")

elif section == "🗑️ Remove URLs":
    st.subheader("🗑️ Remove URLs")
    
    # Load current URLs
    url_data = load_url_data()
    
    if not url_data.empty:
        st.warning("⚠️ Removing URLs will stop price tracking for those product-retailer combinations.")
        
        # Select URLs to remove
        url_options = {}
        for _, row in url_data.iterrows():
            display_name = f"{row['brand']} - {row['product_name']} ({row['pack_size']}) @ {row['retailer_name']}"
            url_options[display_name] = row['id']
        
        selected_urls = st.multiselect(
            "Select URLs to Remove:",
            list(url_options.keys()),
            help="You can select multiple URLs to remove at once"
        )
        
        if selected_urls:
            st.subheader("URLs to be removed:")
            for url_name in selected_urls:
                url_id = url_options[url_name]
                url_row = url_data[url_data['id'] == url_id].iloc[0]
                st.write(f"- {url_name}")
                st.write(f"  URL: {url_row['product_url']}")
            
            if st.button("🗑️ Confirm Removal", type="primary"):
                try:
                    selected_ids = [url_options[name] for name in selected_urls]
                    
                    with db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        placeholders = ','.join(['?' for _ in selected_ids])
                        cursor.execute(f"""
                            DELETE FROM sku_retailer_urls 
                            WHERE id IN ({placeholders})
                        """, selected_ids)
                        conn.commit()
                        
                        st.success(f"✅ Successfully removed {len(selected_urls)} URL(s)")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error removing URLs: {str(e)}")
    else:
        st.info("No URLs to remove.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**URL Manager**")
st.sidebar.markdown("Manage product URLs easily")

# Help section
with st.sidebar.expander("💡 Help & Tips"):
    st.markdown("""
    **Adding URLs:**
    - Copy the full product page URL from the retailer's website
    - Make sure the URL points to the specific product and pack size
    - Test the URL in your browser first
    
    **URL Format Examples:**
    - Tesco: `https://www.tesco.com/groceries/en-GB/products/123456789`
    - Sainsbury's: `https://www.sainsburys.co.uk/gol-ui/product/product-name-123456`
    - Boots: `https://www.boots.com/product-name-123456`
    
    **Best Practices:**
    - Keep URLs up to date if products move
    - Disable URLs temporarily instead of deleting them
    - Check URLs regularly for accuracy
    """)

# System status
with st.sidebar.expander("📊 System Status"):
    url_data = load_url_data()
    if not url_data.empty:
        total_urls = len(url_data)
        active_urls = len(url_data[url_data['active'] == 1])
        st.write(f"**Total URLs:** {total_urls}")
        st.write(f"**Active URLs:** {active_urls}")
        st.write(f"**Inactive URLs:** {total_urls - active_urls}")
    else:
        st.write("**No URLs configured**")