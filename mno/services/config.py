import os
from pathlib import Path

class Config:
    PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
    SMDP_BASE_URL = "http://localhost:8000"
    REFRESH_INTERVAL_MS = 2000
