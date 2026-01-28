#!/bin/bash
# Setup script for FastAPI and SQLite on Google Cloud 

set -e  # Exit on error

echo "Starting FastAPI and SQLite setup..."

# Navigate to project directory
cd ~/sundai || (mkdir -p ~/sundai && cd ~/sundai)

# Check if files exist, if not, we'll need to upload them
if [ ! -f "app/api/server.py" ]; then
    echo "Warning: app/api/server.py not found. Make sure you've uploaded all project files."
fi

# Install Python dependencies
echo "Installing Python dependencies..."
python3 -m pip install --user --upgrade pip
python3 -m pip install --user -r requirements.txt

# Create database directory if it doesn't exist
mkdir -p ~/sundai/data

# Initialize the database
echo "Initializing SQLite database..."
python3 << 'EOF'
from app.database import init_db
init_db()
print("Database initialized successfully")
EOF

# Check if FastAPI is already running
if pgrep -f "uvicorn app.api.server:app" > /dev/null; then
    echo "FastAPI server is already running. Stopping it..."
    pkill -f "uvicorn app.api.server:app"
    sleep 2
fi

# Start FastAPI server
echo "Starting FastAPI server..."
nohup python3 -m uvicorn app.api.server:app --host 0.0.0.0 --port 8000 > ~/sundai/fastapi.log 2>&1 &

# Wait a moment for server to start
sleep 3

# Check if server started successfully
if pgrep -f "uvicorn app.api.server:app" > /dev/null; then
    echo "FastAPI server started successfully!"
    echo "Logs are available at: ~/sundai/fastapi.log"
    echo "Check logs with: tail -f ~/sundai/fastapi.log"
    echo "API should be available at: http://$(curl -s ifconfig.me):8000"
    echo ""
    echo "Useful commands:"
    echo "  - View logs: tail -f ~/sundai/fastapi.log"
    echo "  - Stop server: pkill -f 'uvicorn app.api.server:app'"
    echo "  - Check status: curl http://localhost:8000/health"
    echo "  - API docs: http://$(curl -s ifconfig.me):8000/docs"
else
    echo "Failed to start FastAPI server. Check logs: tail -f ~/sundai/fastapi.log"
    exit 1
fi

echo ""
echo "Setup complete"
