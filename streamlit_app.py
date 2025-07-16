#!/usr/bin/env python3
"""
Streamlit Cloud entry point for the Price Tracker Dashboard.
This file is required for Streamlit Cloud deployment.
"""

import streamlit as st
import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Test basic functionality first
st.title("🏥 Price Tracker Dashboard")
st.write("Testing basic functionality...")

try:
    # Test imports one by one
    st.write("✅ Basic imports working")
    
    from database.models import DatabaseManager
    st.write("✅ Database models imported")
    
    from utils.export_manager import ExportManager
    st.write("✅ Export manager imported")
    
    from utils.health_monitor import HealthMonitor
    st.write("✅ Health monitor imported")
    
    from utils.data_validator import DataQualityChecker
    st.write("✅ Data validator imported")
    
    # Test database initialization
    db_manager = DatabaseManager()
    st.write("✅ Database manager created")
    
    # Test database operations
    db_manager.create_tables()
    st.write("✅ Database tables created")
    
    # Import and run the full dashboard
    st.write("🚀 Loading full dashboard...")
    import dashboard.simple_app
    
except Exception as e:
    st.error(f"❌ Error: {str(e)}")
    st.write("**Traceback:**")
    import traceback
    st.code(traceback.format_exc())