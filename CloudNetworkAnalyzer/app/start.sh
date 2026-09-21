#!/bin/bash

# Adaptive Middleware Prototype - Startup Script
# This script starts both the backend and frontend

echo "=============================================="
echo "  Adaptive Middleware Prototype Launcher"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED}Error: npm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Install backend dependencies if needed
if [ ! -d "backend/__pycache__" ]; then
    echo -e "${BLUE}Installing Python dependencies...${NC}"
    cd backend
    pip3 install -r requirements.txt -q
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to install Python dependencies${NC}"
        exit 1
    fi
    cd ..
    echo -e "${GREEN}✓ Python dependencies installed${NC}"
fi

# Install frontend dependencies if needed
if [ ! -d "node_modules" ]; then
    echo -e "${BLUE}Installing Node.js dependencies...${NC}"
    npm install -q
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to install Node.js dependencies${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Node.js dependencies installed${NC}"
fi

echo ""
echo "=============================================="
echo "  Starting Services"
echo "=============================================="
echo ""

# Function to cleanup processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    echo -e "${GREEN}✓ Services stopped${NC}"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${BLUE}Starting Backend Server...${NC}"
cd backend
python3 main.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 2

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Error: Backend failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Backend running on http://localhost:8000${NC}"
echo ""

# Start frontend
echo -e "${BLUE}Starting Frontend Development Server...${NC}"
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 3

# Check if frontend is running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}Error: Frontend failed to start${NC}"
    cleanup
    exit 1
fi

echo -e "${GREEN}✓ Frontend running on http://localhost:5173${NC}"
echo ""

echo "=============================================="
echo "  Services Started Successfully!"
echo "=============================================="
echo ""
echo -e "  ${GREEN}Backend:${NC}  http://localhost:8000"
echo -e "  ${GREEN}Frontend:${NC} http://localhost:5173"
echo -e "  ${GREEN}API Docs:${NC} http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both services"
echo ""
echo "=============================================="

# Wait for both processes
wait
