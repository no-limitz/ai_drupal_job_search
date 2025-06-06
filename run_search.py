#!/usr/bin/env python3
"""
Simplified runner script for the Drupal job search system
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_orchestrator import main

if __name__ == "__main__":
    sys.exit(main())
