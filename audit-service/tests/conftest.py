import sys
from pathlib import Path

# audit-service/ (parent of this tests/ dir) has to be importable as top-level
# modules (import vision_provider, import engine, ...) regardless of where
# pytest is invoked from — mirrors how main.py/uvicorn already run with
# audit-service/ as the working directory in Docker.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
