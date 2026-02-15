/**
 * Computer Vision Service
 * Handles dish recognition using a simplified CV approach
 * In production, this would use TensorFlow.js or a trained model
 * For this implementation, we use feature matching and heuristics
 */

const sharp = require('sharp');
const Dish = require('../models/Dish');

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
      // Try to load dishes from database, but fallback to empty if DB unavailable
      try {
        this.dishDatabase = await Dish.find({}).lean().maxTimeMS(2000);
        console.log('✅ Vision service initialized with', this.dishDatabase.length, 'dishes');
      } catch (dbError) {
        console.warn('⚠️  Database unavailable, using fallback dish list');
        // Fallback: use simple hardcoded dish categories for detection without DB
        this.dishDatabase = [
          { _id: 'fallback-veg', dishName: 'Vegetable', category: 'vegetable' },
          { _id: 'fallback-protein', dishName: 'Protein', category: 'protein' },
          { _id: 'fallback-starch', dishName: 'Starch', category: 'starch' },
        ];
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

      // Extract image features
      const imageFeatures = await this.extractImageFeatures(imagePath);

      // Match features against dish database
      const matches = await this.matchDishes(imageFeatures);

      // Sort by confidence and return top matches
      const topMatches = matches
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 5); // Return top 5 matches

      const processingTime = Date.now() - startTime;

      return {
        identifiedDishes: topMatches,
        processingTime,
        imageFeatures
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
   * Match extracted features against dish database
   * @param {Object} imageFeatures - Extracted image features
   * @returns {Array} - Array of dish matches with confidence scores
   */
  async matchDishes(imageFeatures) {
    const matches = [];
    const { colorProfile, avgBrightness, textureComplexity } = imageFeatures;

    for (const dish of this.dishDatabase) {
      let confidence = 0.3; // Base confidence

      // Match based on category and color profile
      if (dish.category === 'vegetable' && colorProfile.isGreenish) {
        confidence += 0.4;
      }

      if (dish.category === 'protein') {
        if (colorProfile.isReddish || colorProfile.isBrownish) {
          confidence += 0.3;
        }
      }

      if (dish.category === 'starch') {
        if (colorProfile.isWhitish || colorProfile.isBrownish) {
          confidence += 0.35;
        }
      }

      // Adjust based on subcategory
      if (dish.subcategory === 'leafy-green' && colorProfile.isGreenish) {
        confidence += 0.15;
      }

      if (dish.subcategory === 'tofu' && colorProfile.isWhitish) {
        confidence += 0.2;
      }

      // Add some randomness to simulate varying detection accuracy
      const randomFactor = (Math.random() * 0.2) - 0.1; // -0.1 to +0.1
      confidence = Math.max(0.1, Math.min(0.95, confidence + randomFactor));

      // Only include dishes with reasonable confidence
      if (confidence > 0.2) {
        matches.push({
          dish: dish._id,
          dishName: dish.name,
          confidence: Math.round(confidence * 100) / 100,
          category: dish.category,
          boundingBox: this.generateBoundingBox(imageFeatures.dimensions)
        });
      }
    }

    // Return random subset if too many matches (simulate real detection)
    if (matches.length > 8) {
      return this.selectTopMatches(matches, 5);
    }

    return matches;
  }

  /**
   * Select top matches using weighted random selection
   * @param {Array} matches - All matches
   * @param {Number} count - Number of matches to return
   * @returns {Array} - Selected matches
   */
  selectTopMatches(matches, count) {
    // Sort by confidence
    matches.sort((a, b) => b.confidence - a.confidence);
    
    // Take top matches plus some random ones for variety
    const topN = Math.ceil(count * 0.7);
    const top = matches.slice(0, topN);
    const remaining = matches.slice(topN);
    
    // Randomly select from remaining
    const randomCount = count - topN;
    for (let i = 0; i < randomCount && remaining.length > 0; i++) {
      const randomIndex = Math.floor(Math.random() * remaining.length);
      top.push(remaining.splice(randomIndex, 1)[0]);
    }
    
    return top;
  }

  /**
   * Generate bounding box coordinates (simulated)
   * @param {Object} dimensions - Image dimensions
   * @returns {Object} - Bounding box coordinates
   */
  generateBoundingBox(dimensions) {
    const { width, height } = dimensions;
    
    // Generate random but realistic bounding box
    const boxWidth = Math.floor(width * (0.3 + Math.random() * 0.4));
    const boxHeight = Math.floor(height * (0.3 + Math.random() * 0.4));
    const x = Math.floor(Math.random() * (width - boxWidth));
    const y = Math.floor(Math.random() * (height - boxHeight));

    return { x, y, width: boxWidth, height: boxHeight };
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

