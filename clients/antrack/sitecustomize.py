"""Ensure the ANTRACK virtual environment overrides the global Pothos module."""
from pathlib import Path
import sys

_site_packages = str(Path(__file__).resolve().parent)
try:
    sys.path.remove(_site_packages)
except ValueError:
    pass
sys.path.insert(0, _site_packages)
