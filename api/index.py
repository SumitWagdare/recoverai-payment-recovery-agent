import os
import sys
from pathlib import Path

# Add the project root to the python path so 'app' can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.server import app

# Vercel looks for 'app' by default in WSGI files.
