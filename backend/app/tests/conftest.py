# Ensure the backend/app directory is on sys.path so tests can import app packages like `services`
import sys
from pathlib import Path

# tests/ -> app/
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
