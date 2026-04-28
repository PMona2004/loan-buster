"""
Pytest configuration — ensures 'app.*' imports resolve correctly.
Without this file, pytest tests/ will fail with ModuleNotFoundError
because Python can't locate the `app` package from the tests/ directory.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
