/**
 * Main server entry point for cAIpng backend
 * Sets up Express server, middleware, routes, and database connection
 */

const express = require('express');
const dotenv = require('dotenv');
const cors = require('cors');
const morgan = require('morgan');
const helmet = require('helmet');
const compression = require('compression');
const path = require('path');

// Load environment variables
dotenv.config();

const mongoose = require('mongoose');

// Import configuration and middleware
const connectDB = require('./config/database');
const { errorHandler } = require('./middleware/errorHandler');
const rateLimiter = require('./middleware/rateLimiter');

// Import routes
const liveRoutes = require('./routes/liveRoutes');

// Initialize Express app
const app = express();

// Connect to MongoDB
connectDB();

// Security middleware
app.use(helmet());

// CORS configuration
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  credentials: true
}));

// Body parsing middleware
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Compression middleware
app.use(compression());

// Logging middleware
if (process.env.NODE_ENV === 'development') {
  app.use(morgan('dev'));
} else {
  app.use(morgan('combined'));
}

// Rate limiting
app.use('/api/', rateLimiter);

// Static files for uploads (may be unused in V2, kept for temp storage)
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));

// Health check endpoint
app.get('/health', (req, res) => {
  const dbState = mongoose.connection.readyState; // 0=disconnected,1=connected,2=connecting,3=disconnecting
  const dbOk = dbState === 1;
  res.status(dbOk ? 200 : 503).json({
    success: dbOk,
    message: dbOk ? 'cAIpng server is running' : 'cAIpng server is running (database degraded)',
    database: dbOk ? 'connected' : 'unavailable',
    timestamp: new Date().toISOString()
  });
});

// Training logs endpoint
const fs = require('fs');
const TRAINING_LOG = path.resolve(__dirname, '../../training/logs/training.log');
app.get('/api/logs', (req, res) => {
  if (!fs.existsSync(TRAINING_LOG)) {
    return res.json({ success: true, logs: '(no training logs yet — run train_tui.py first)' });
  }
  const content = fs.readFileSync(TRAINING_LOG, 'utf-8');
  res.json({ success: true, logs: content });
});

// API Routes (V2)
app.use('/api/live', liveRoutes);

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: 'Route not found'
  });
});

// Error handling middleware (must be last)
app.use(errorHandler);

// Start server
const PORT = process.env.PORT || 5000;
const server = app.listen(PORT, () => {
  console.log(`🚀 cAIpng server running in ${process.env.NODE_ENV} mode on port ${PORT}`);
});

// Handle unhandled promise rejections
process.on('unhandledRejection', (err) => {
  console.error('Unhandled Rejection:', err.message);
  server.close(() => process.exit(1));
});

module.exports = app;

