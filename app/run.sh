#!/bin/bash

# Function to handle cleanup on script exit
cleanup() {
    echo "Stopping servers..."
    kill 0
}

# Trap EXIT and SIGINT signals to ensure cleanup runs
trap cleanup EXIT SIGINT

echo "Cleaning up dangling ports (8000, 5173)..."
lsof -ti:8000,5173 | xargs kill -9 2>/dev/null || true

echo "Starting backend..."
cd backend || exit 1
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "../../venv" ]; then
    source ../../venv/bin/activate
else
    echo "Failed to find venv, you may need to run setup."
    exit 1
fi
uvicorn assessment_app.main:app --reload &
BACKEND_PID=$!
cd ..

echo "Starting frontend..."
cd frontend || exit 1
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Both servers are running."
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both servers."

# Wait for all background processes
wait
