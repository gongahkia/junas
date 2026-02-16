/**
 * Computer Vision Service
 * Handles dish recognition using trained neural network
 * Falls back to heuristic approach if model is not available
 */

const sharp = require('sharp');
const Dish = require('../models/Dish');
const modelService = require('./modelService');

// Module-level dish cache with 60s TTL
let dishCache = null;
let dishCacheExpiry = 0;

/**
 * Vision service with neural network support
 * Uses trained CNN model when available, falls back to heuristics
 */
class VisionService {
  constructor() {
    this.modelLoaded = false;
    this.dishDatabase = null;
    this.useNeuralNetwork = false;
  }

  /**
   * Initialize the vision service
   * Load dish database and neural network model
   */
  async initialize() {
    try {
      const now = Date.now();
      if (dishCache && now < dishCacheExpiry) {
        this.dishDatabase = dishCache;
      } else {
        try {
          this.dishDatabase = await Dish.find({}).lean().maxTimeMS(2000);
          dishCache = this.dishDatabase;
          dishCacheExpiry = now + 60000;
          console.log('✅ Vision service initialized with', this.dishDatabase.length, 'dishes');
        } catch (dbError) {
          console.warn('⚠️  Database unavailable, using fallback dish list');
          this.dishDatabase = [
            { _id: 'fallback-veg', dishName: 'Vegetable', category: 'vegetable' },
            { _id: 'fallback-protein', dishName: 'Protein', category: 'protein' },
            { _id: 'fallback-starch', dishName: 'Starch', category: 'starch' },
          ];
        }
      }
      
      // Try to initialize neural network
      const modelReady = await modelService.initialize();
      this.useNeuralNetwork = modelReady;
      
      if (this.useNeuralNetwork) {
        console.log('✅ Using NEURAL NETWORK for food recognition');
      } else {
        console.log('⚠️  Using HEURISTIC fallback for food recognition');
      }
      
      this.modelLoaded = true;
    } catch (error) {
      console.error('❌ Failed to initialize vision service:', error);
      // Don't throw; allow degraded mode
      this.dishDatabase = [];
      this.modelLoaded = true;
    }
  }

  /**
   * Analyze image and identify dishes
   * Uses neural network if available, otherwise falls back to heuristics
   * @param {String} imagePath - Path to image file
   * @returns {Array} - Array of identified dishes with confidence scores
   */
  async analyzeDish(imagePath) {
    if (!this.modelLoaded) {
      await this.initialize();
    }

    try {
      // Use neural network if available
      if (this.useNeuralNetwork) {
        return await modelService.analyzeDish(imagePath);
      }
      
      // Fall back to heuristic method
      return await this.analyzeDishHeuristic(imagePath);
      
    } catch (error) {
      console.error('Error analyzing dish:', error);
      
      // If neural network fails, fall back to heuristics
      if (this.useNeuralNetwork) {
        console.warn('⚠️  Neural network failed, falling back to heuristics');
        return await this.analyzeDishHeuristic(imagePath);
      }
      
      throw new Error('Failed to analyze dish image');
    }
  }

  /**
   * Original heuristic-based analysis (fallback)
   */
  async analyzeDishHeuristic(imagePath) {
    const startTime = Date.now();

      // Extract per-region features using NxN grid
      const N = 3;
      const image = sharp(imagePath);
      const metadata = await image.metadata();
      const { width, height } = metadata;
      const cellW = Math.floor(width / N);
      const cellH = Math.floor(height / N);

      const regionDetections = [];

      for (let row = 0; row < N; row++) {
        for (let col = 0; col < N; col++) {
          const rx = col * cellW;
          const ry = row * cellH;
          const rw = col === N - 1 ? width - rx : cellW;
          const rh = row === N - 1 ? height - ry : cellH;

          const regionBuf = await sharp(imagePath)
            .extract({ left: rx, top: ry, width: rw, height: rh })
            .toBuffer();
          const stats = await sharp(regionBuf).stats();

          const [r, g, b] = stats.channels;
          const avgBrightness = (r.mean + g.mean + b.mean) / 3;
          const colorProfile = {
            isGreenish: g.mean > r.mean && g.mean > b.mean,
            isReddish: r.mean > g.mean && r.mean > b.mean,
            isBrownish: Math.abs(r.mean - g.mean) < 20 && r.mean > b.mean,
            isWhitish: avgBrightness > 180,
            isDarkish: avgBrightness < 100
          };

          // Find best matching dish for this cell
          let bestDish = null;
          let bestConf = 0;

          for (const dish of this.dishDatabase) {
            let confidence = 0.3;
            if (dish.category === 'vegetable' && colorProfile.isGreenish) confidence += 0.4;
            if (dish.category === 'protein' && (colorProfile.isReddish || colorProfile.isBrownish)) confidence += 0.3;
            if (dish.category === 'starch' && (colorProfile.isWhitish || colorProfile.isBrownish)) confidence += 0.35;
            if (dish.subcategory === 'leafy-green' && colorProfile.isGreenish) confidence += 0.15;
            if (dish.subcategory === 'tofu' && colorProfile.isWhitish) confidence += 0.2;

            const randomFactor = (Math.random() * 0.2) - 0.1;
            confidence = Math.max(0.1, Math.min(0.95, confidence + randomFactor));

            if (confidence > bestConf) {
              bestConf = confidence;
              bestDish = dish;
            }
          }

          if (bestDish && bestConf > 0.3) {
            regionDetections.push({
              dish: bestDish._id,
              dishName: bestDish.name,
              confidence: Math.round(bestConf * 100) / 100,
              category: bestDish.category,
              boundingBox: { x: rx, y: ry, width: rw, height: rh }
            });
          }
        }
      }

      // Apply IoU-based NMS to deduplicate overlapping detections
      const nmsResults = this.nonMaxSuppression(regionDetections, 0.5);

      // Keep top 5 by confidence
      const topMatches = nmsResults
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 5);

      const processingTime = Date.now() - startTime;

      return {
        identifiedDishes: topMatches,
        processingTime,
        imageFeatures: { dimensions: { width, height }, method: 'heuristic' }
      };
    } catch (error) {
      console.error('Error in heuristic analysis:', error);
      throw error;
    }
  }

  /**
   * IoU-based Non-Maximum Suppression
   */
  nonMaxSuppression(detections, iouThreshold = 0.5) {
    if (!detections || detections.length === 0) return [];
    const sorted = [...detections].sort((a, b) => b.confidence - a.confidence);
    const keep = [];

    for (const det of sorted) {
      let dominated = false;
      for (const kept of keep) {
        if (det.category !== kept.category) continue;
        const a = det.boundingBox;
        const b = kept.boundingBox;
        const x1 = Math.max(a.x, b.x);
        const y1 = Math.max(a.y, b.y);
        const x2 = Math.min(a.x + a.width, b.x + b.width);
        const y2 = Math.min(a.y + a.height, b.y + b.height);
        const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
        const union = a.width * a.height + b.width * b.height - inter;
        if (union > 0 && inter / union > iouThreshold) {
          dominated = true;
          break;
        }
      }
      if (!dominated) keep.push(det);
    }
    return keep;
  }

  /**
   * Extract features from image for matching
   * @param {String} imagePath - Path to image
   * @returns {Object} - Extracted features
   */
  async extractImageFeatures(imagePath) {
    try {
      const image = sharp(imagePath);
      const metadata = await image.metadata();
      const stats = await image.stats();

      // Extract dominant colors
      const dominantColors = stats.channels.map(channel => ({
        mean: channel.mean,
        std: channel.std,
        min: channel.min,
        max: channel.max
      }));

      // Calculate average brightness
      const avgBrightness = stats.channels.reduce((sum, ch) => sum + ch.mean, 0) / stats.channels.length;

      // Analyze color distribution (RGB channels)
      const [r, g, b] = stats.channels;
      
      // Determine predominant color characteristics
      const colorProfile = {
        isGreenish: g.mean > r.mean && g.mean > b.mean, // Vegetables
        isReddish: r.mean > g.mean && r.mean > b.mean,   // Meat, tomato-based
        isBrownish: Math.abs(r.mean - g.mean) < 20 && r.mean > b.mean, // Fried items, rice
        isWhitish: avgBrightness > 180, // Rice, tofu
        isDarkish: avgBrightness < 100  // Soy sauce dishes
      };

      // Calculate texture complexity (using standard deviation)
      const textureComplexity = (r.std + g.std + b.std) / 3;

      return {
        dominantColors,
        avgBrightness,
        colorProfile,
        textureComplexity,
        dimensions: {
          width: metadata.width,
          height: metadata.height
        }
      };
    } catch (error) {
      console.error('Error extracting image features:', error);
      throw error;
    }
  }

  /**
   * Batch analyze multiple regions in image
   * @param {String} imagePath - Path to image
   * @param {Array} regions - Array of region coordinates
   * @returns {Array} - Analysis results for each region
   */
  async batchAnalyze(imagePath, regions) {
    const results = [];
    
    for (const region of regions) {
      try {
        const result = await this.analyzeDish(imagePath);
        results.push({ region, ...result });
      } catch (error) {
        console.error('Error analyzing region:', error);
        results.push({ region, error: error.message });
      }
    }
    
    return results;
  }
}

// Singleton instance
const visionService = new VisionService();

module.exports = visionService;

