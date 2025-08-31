import os
import sys

# Ensure the repository root is on sys.path so imports like `import app` and `import agents` work
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

