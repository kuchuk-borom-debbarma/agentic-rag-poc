#!/bin/bash

# Exit if any command fails
set -e

# Store the project root directory
PROJECT_ROOT="$(pwd)"

echo "Starting AWS Customer Agreement RAG App..."

# Start Backend
echo "Starting FastAPI Backend..."
cd "$PROJECT_ROOT/app/backend"
# Use the root venv if it exists, otherwise try the backend-specific one
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
else
    echo "Warning: No virtual environment found. Running without it."
fi

# Start the uvicorn server in the background
uvicorn assessment_app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start Frontend
echo "Starting React Frontend..."
cd "$PROJECT_ROOT/app/frontend"
# Ensure dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "node_modules not found. Running npm install..."
    npm install
fi

# Start Vite server in the background
npm run dev &
FRONTEND_PID=$!

echo "========================================="
echo "Services are starting!"
echo "Backend API: http://localhost:8000"
echo "Frontend UI: http://localhost:5173"
echo "Press Ctrl+C to shut down both services."
echo "========================================="

# Handle graceful shutdown on Ctrl+C
function cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "Shutdown complete."
    exit 0
}

# Trap the SIGINT signal (Ctrl+C)
trap cleanup SIGINT SIGTERM

# Wait for background processes to keep the script running
wait $BACKEND_PID
wait $FRONTEND_PID
