# file: scripts/run_api.sh
#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run FastAPI server
echo "Starting FastAPI server on port 8000..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000