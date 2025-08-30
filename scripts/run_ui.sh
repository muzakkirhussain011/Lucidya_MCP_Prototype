# file: scripts/run_ui.sh
#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run Streamlit UI
echo "Starting Streamlit UI on port 8501..."
streamlit run ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0