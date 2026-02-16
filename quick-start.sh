#!/bin/bash

# cAI-png Quick Start Script
# This script sets up the entire application automatically

set -e  # Exit on error

echo "🍱 cAI-png Quick Start Setup"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "Checking prerequisites..."

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi
echo -e "${GREEN}✅ Node.js $(node --version)${NC}"

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ npm $(npm --version)${NC}"

# Check MongoDB
if ! command -v mongosh &> /dev/null && ! command -v mongo &> /dev/null; then
    echo -e "${YELLOW}⚠️  MongoDB CLI not found${NC}"
    echo "You can use MongoDB Atlas instead, or install MongoDB locally"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ MongoDB CLI found${NC}"
fi

echo ""
echo "=============================="
echo "Setting up Backend..."
echo "=============================="

cd backend

# Install dependencies
echo "📦 Installing backend dependencies..."
npm install

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
NODE_ENV=development
PORT=5000
MONGODB_URI=mongodb://localhost:27017/caipng
JWT_SECRET=$(openssl rand -base64 32)
JWT_EXPIRE=7d
MAX_FILE_SIZE=10485760
UPLOAD_PATH=./uploads
CORS_ORIGIN=http://localhost:3000
RATE_LIMIT_WINDOW=15
RATE_LIMIT_MAX_REQUESTS=100
EOF
    echo -e "${GREEN}✅ .env file created${NC}"
else
    echo -e "${YELLOW}⚠️  .env already exists, skipping${NC}"
fi

# Create uploads directory
mkdir -p uploads
echo -e "${GREEN}✅ Uploads directory created${NC}"

# Seed database
echo "🌱 Seeding database..."
npm run seed || echo -e "${YELLOW}⚠️  Database seeding failed. Make sure MongoDB is running.${NC}"

cd ..

echo ""
echo "=============================="
echo "Setting up Frontend..."
echo "=============================="

cd frontend

# Install dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    echo "VITE_API_URL=http://localhost:5000/api" > .env
    echo -e "${GREEN}✅ .env file created${NC}"
else
    echo -e "${YELLOW}⚠️  .env already exists, skipping${NC}"
fi

cd ..

echo ""
echo "=============================="
echo "✅ Setup Complete!"
echo "=============================="
echo ""
echo "To start the application:"
echo ""
echo "Terminal 1 (Backend):"
echo -e "${GREEN}  cd backend && npm run dev${NC}"
echo ""
echo "Terminal 2 (Frontend):"
echo -e "${GREEN}  cd frontend && npm run dev${NC}"
echo ""
echo "Then open: ${GREEN}http://localhost:3000${NC}"
echo ""
echo "Or use the Makefile:"
echo -e "${GREEN}  make dev-backend${NC}  (terminal 1)"
echo -e "${GREEN}  make dev-frontend${NC} (terminal 2)"
echo ""
echo "Happy coding! 🍱"

