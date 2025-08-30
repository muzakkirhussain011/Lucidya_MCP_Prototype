# file: scripts/start_mcp_servers.sh
#!/bin/bash

# Kill any existing MCP servers
echo "Stopping any existing MCP servers..."
pkill -f "mcp/servers/search_server.py" 2>/dev/null
pkill -f "mcp/servers/email_server.py" 2>/dev/null
pkill -f "mcp/servers/calendar_server.py" 2>/dev/null
pkill -f "mcp/servers/store_server.py" 2>/dev/null

sleep 1

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start MCP servers in background
echo "Starting MCP servers..."

echo "  - Search Server (port 9001)"
python mcp/servers/search_server.py &

echo "  - Email Server (port 9002)"
python mcp/servers/email_server.py &

echo "  - Calendar Server (port 9003)"
python mcp/servers/calendar_server.py &

echo "  - Store Server (port 9004)"
python mcp/servers/store_server.py &

sleep 2

# Check if servers are running
echo ""
echo "Checking server status..."
for port in 9001 9002 9003 9004; do
    if lsof -i:$port > /dev/null 2>&1; then
        echo "  ✓ Server on port $port is running"
    else
        echo "  ✗ Server on port $port failed to start"
    fi
done

echo ""
echo "MCP servers started. To stop them, run:"
echo "  pkill -f 'mcp/servers'"