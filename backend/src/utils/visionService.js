/**
 * Computer Vision Service
 * Handles dish recognition using a simplified CV approach
 * In production, this would use TensorFlow.js or a trained model
 * For this implementation, we use feature matching and heuristics
 */

const sharp = require('sharp');
const Dish = require('../models/Dish');

// Module-level dish cache with 60s TTL
let dishCache = null;
let dishCacheExpiry = 0;

/**
 * Simple dish recognition service
 * Uses color analysis and pattern matching as a simplified CV approach
 * In production, replace with actual trained CNN model
 */
class VisionService {
  constructor() {
    this.modelLoaded = false;
    this.dishDatabase = null;
  }

  /**
   * Initialize the vision service
   * Load dish database for matching
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
   * @param {String} imagePath - Path to image file
   * @returns {Array} - Array of identified dishes with confidence scores
   */
  async analyzeDish(imagePath) {
    if (!this.modelLoaded) {
      await this.initialize();
    }

    try {
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

      // Keep top 5 by confidence
      const topMatches = regionDetections
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 5);

      const processingTime = Date.now() - startTime;

      return {
        identifiedDishes: topMatches,
        processingTime,
        imageFeatures: { dimensions: { width, height } }
      };
    } catch (error) {
      console.error('Error analyzing dish:', error);
      throw new Error('Failed to analyze dish image');
    }
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

