#!/usr/bin/env python3
"""
Streamlit Cloud entry point for the Price Tracker Dashboard.
This file is required for Streamlit Cloud deployment.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import the dashboard module - Streamlit will run it automatically
import dashboard.simple_app