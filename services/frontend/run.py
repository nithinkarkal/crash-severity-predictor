#!/usr/bin/env python3
"""
ASP frontend launcher
"""

import sys
from pathlib import Path

# add the root directory to the path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.frontend.src.app import main

if __name__ == "__main__":
    main()
