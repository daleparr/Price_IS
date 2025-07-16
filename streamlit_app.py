#!/usr/bin/env python3
"""
Streamlit Cloud entry point for the Price Tracker Dashboard.
This file is required for Streamlit Cloud deployment.
"""

import streamlit as st
import sys
import os

# Page configuration MUST be first
st.set_page_config(
    page_title="Price Tracker Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Initialize database and components
try:
    from database.models import DatabaseManager
    from database.migrations import populate_initial_data
    
    # Initialize database
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    # Check if we need to populate initial data
    retailers = db_manager.get_active_retailers()
    if len(retailers) == 0:
        populate_initial_data(db_manager)
        st.success("✅ Database initialized with configuration data")
    
    # Now import and run the full dashboard
    # Clear any previous content first
    st.empty()
    
    # Import the dashboard module - this will execute all the dashboard code
    exec(open('src/dashboard/simple_app.py').read())
    
except Exception as e:
    st.error(f"❌ Error initializing dashboard: {str(e)}")
    st.write("**Traceback:**")
    import traceback
    st.code(traceback.format_exc())