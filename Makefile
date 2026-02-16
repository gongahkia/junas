.PHONY: help dev dev-backend dev-frontend build clean install test seed

# Default target - show help
help:
	@echo "cAI-png Development Commands"
	@echo "=============================="
	@echo ""
	@echo "  make dev           - Start both frontend and backend in development mode"
	@echo "  make dev-backend   - Start only backend"
	@echo "  make dev-frontend  - Start only frontend"
	@echo "  make install       - Install all dependencies"
	@echo "  make seed          - Seed the database with sample dishes"
	@echo "  make test          - Run all tests"
	@echo "  make build         - Build production bundles"
	@echo ""
	@echo "  Maintenance:"
	@echo "  make clean         - Clean node_modules and build artifacts"
	@echo ""

# Development commands
dev:
	@echo "🚀 Starting cAI-png in development mode..."
	@echo "Frontend: http://localhost:3000"
	@echo "Backend: http://localhost:5000"
	@echo ""
	@echo "Run these in separate terminals:"
	@echo "  Terminal 1: make dev-backend"
	@echo "  Terminal 2: make dev-frontend"

dev-backend:
	@echo "🔧 Starting backend server..."
	cd backend && npm run dev

dev-frontend:
	@echo "🎨 Starting frontend server..."
	cd frontend && npm run dev

# Install dependencies
install:
	@echo "📦 Installing backend dependencies..."
	cd backend && npm install
	@echo ""
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install
	@echo ""
	@echo "✅ All dependencies installed!"

# Database seeding
seed:
	@echo "🌱 Seeding database with sample dishes..."
	cd backend && npm run seed

# Testing
test:
	@echo "🧪 Running backend tests..."
	cd backend && npm test
	@echo ""
	@echo "🧪 Running frontend tests..."
	cd frontend && npm test

# Build for production
build:
	@echo "🏗️  Building backend..."
	cd backend && npm run build
	@echo ""
	@echo "🏗️  Building frontend..."
	cd frontend && npm run build
	@echo ""
	@echo "✅ Build complete!"

# Maintenance
clean:
	@echo "🧹 Cleaning project..."
	rm -rf backend/node_modules backend/uploads/*
	rm -rf frontend/node_modules frontend/dist
	@echo "✅ Cleaned!"
