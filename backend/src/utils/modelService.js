/**
 * Neural Network Model Service
 * Handles ONNX model inference for food recognition
 * Replaces the heuristic-based vision service with real deep learning
 */

const ort = require('onnxruntime-node');
const sharp = require('sharp');
const path = require('path');
const fs = require('fs');

const MODEL_PATH = path.join(__dirname, '../../models/caifan_model.onnx');
const CLASSES_PATH = path.join(__dirname, '../../models/classes.json');

// Image preprocessing constants (same as training)
const MEAN = [0.485, 0.456, 0.406];
const STD = [0.229, 0.224, 0.225];
const IMAGE_SIZE = 224;

class ModelService {
  constructor() {
    this.session = null;
    this.classes = null;
    this.modelLoaded = false;
  }

  /**
   * Initialize the ONNX model session
   */
  async initialize() {
    try {
      // Check if model files exist
      if (!fs.existsSync(MODEL_PATH)) {
        console.warn('⚠️  Model file not found. Using fallback mode.');
        console.warn(`   Expected model at: ${MODEL_PATH}`);
        console.warn('   💡 Tip: Train the model first using training/train_tui.py');
        this.modelLoaded = false;
        return false;
      }

      if (!fs.existsSync(CLASSES_PATH)) {
        console.warn('⚠️  Classes file not found. Using fallback mode.');
        console.warn(`   Expected classes at: ${CLASSES_PATH}`);
        this.modelLoaded = false;
        return false;
      }

      // Load class mapping
      const classesData = fs.readFileSync(CLASSES_PATH, 'utf8');
      this.classes = JSON.parse(classesData);

      // Create ONNX inference session
      this.session = await ort.InferenceSession.create(MODEL_PATH, {
        executionProviders: ['cpu'],
        graphOptimizationLevel: 'all'
      });

      console.log('✅ Neural network model loaded successfully');
      console.log(`   Classes: ${Object.keys(this.classes).length}`);
      console.log(`   Model: ${MODEL_PATH}`);
      
      this.modelLoaded = true;
      return true;

    } catch (error) {
      console.error('❌ Failed to initialize model:', error.message);
      this.modelLoaded = false;
      return false;
    }
  }

  /**
   * Preprocess image for model inference
   * @param {String} imagePath - Path to image file
   * @returns {Float32Array} - Preprocessed image tensor
   */
  async preprocessImage(imagePath) {
    try {
      // Resize and convert to RGB
      const imageBuffer = await sharp(imagePath)
        .resize(IMAGE_SIZE, IMAGE_SIZE)
        .removeAlpha()
        .raw()
        .toBuffer();

      // Convert to float array and normalize
      const float32Data = new Float32Array(3 * IMAGE_SIZE * IMAGE_SIZE);
      const pixels = new Uint8Array(imageBuffer);

      // Convert from HWC to CHW format and normalize
      for (let c = 0; c < 3; c++) {
        for (let h = 0; h < IMAGE_SIZE; h++) {
          for (let w = 0; w < IMAGE_SIZE; w++) {
            const pixelIdx = (h * IMAGE_SIZE + w) * 3 + c;
            const tensorIdx = c * IMAGE_SIZE * IMAGE_SIZE + h * IMAGE_SIZE + w;
            
            // Normalize: (pixel / 255.0 - mean) / std
            const normalized = (pixels[pixelIdx] / 255.0 - MEAN[c]) / STD[c];
            float32Data[tensorIdx] = normalized;
          }
        }
      }

      return float32Data;

    } catch (error) {
      console.error('Error preprocessing image:', error);
      throw error;
    }
  }

  /**
   * Run inference on an image
   * @param {String} imagePath - Path to image file
   * @returns {Object} - Top predictions with confidence scores
   */
  async predict(imagePath) {
    if (!this.modelLoaded) {
      throw new Error('Model not loaded. Please initialize first.');
    }

    try {
      const startTime = Date.now();

      // Preprocess image
      const inputData = await this.preprocessImage(imagePath);

      // Create tensor
      const tensor = new ort.Tensor('float32', inputData, [1, 3, IMAGE_SIZE, IMAGE_SIZE]);

      // Run inference
      const feeds = { input: tensor };
      const results = await this.session.run(feeds);
      const output = results.output.data;

      // Apply softmax to get probabilities
      const expScores = Array.from(output).map(x => Math.exp(x));
      const sumExp = expScores.reduce((a, b) => a + b, 0);
      const probabilities = expScores.map(x => x / sumExp);

      // Get top 5 predictions
      const predictions = probabilities
        .map((prob, idx) => ({
          classId: idx,
          className: this.classes[idx] || `class_${idx}`,
          confidence: prob
        }))
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 5);

      const processingTime = Date.now() - startTime;

      return {
        predictions,
        processingTime,
        modelVersion: 'neural-v1.0'
      };

    } catch (error) {
      console.error('Error during inference:', error);
      throw error;
    }
  }

  /**
   * Analyze image with region-based detection
   * Compatible with existing visionService interface
   * @param {String} imagePath - Path to image file
   * @returns {Object} - Analysis results matching visionService format
   */
  async analyzeDish(imagePath) {
    if (!this.modelLoaded) {
      throw new Error('Model not loaded. Cannot analyze dish.');
    }

    try {
      const startTime = Date.now();

      // Get image dimensions for bounding boxes
      const metadata = await sharp(imagePath).metadata();
      const { width, height } = metadata;

      // Run inference
      const result = await this.predict(imagePath);

      // Convert predictions to detections format
      // For now, use whole image as bounding box for top prediction
      // In future, could implement object detection for multiple dishes
      const identifiedDishes = result.predictions
        .filter(p => p.confidence > 0.1) // Filter low confidence
        .map((pred, idx) => {
          // Create bounding boxes for top predictions
          // Distribute across image grid for visualization
          const gridSize = 3;
          const row = Math.floor(idx / gridSize);
          const col = idx % gridSize;
          const boxW = Math.floor(width / gridSize);
          const boxH = Math.floor(height / gridSize);

          return {
            dish: pred.classId,
            dishName: pred.className,
            confidence: Math.round(pred.confidence * 100) / 100,
            category: this.inferCategory(pred.className),
            boundingBox: {
              x: col * boxW,
              y: row * boxH,
              width: boxW,
              height: boxH
            }
          };
        });

      const processingTime = Date.now() - startTime;

      return {
        identifiedDishes,
        processingTime,
        imageFeatures: { 
          dimensions: { width, height },
          modelVersion: 'neural-v1.0'
        }
      };

    } catch (error) {
      console.error('Error analyzing dish:', error);
      throw error;
    }
  }

  /**
   * Infer category from class name
   * @param {String} className - Name of the food class
   * @returns {String} - Inferred category
   */
  inferCategory(className) {
    const lower = className.toLowerCase();
    
    // Simple heuristic mapping
    if (lower.includes('rice') || lower.includes('noodle') || lower.includes('bread')) {
      return 'starch';
    } else if (lower.includes('vegetable') || lower.includes('salad') || 
               lower.includes('green') || lower.includes('bean')) {
      return 'vegetable';
    } else if (lower.includes('chicken') || lower.includes('fish') || 
               lower.includes('meat') || lower.includes('pork') || 
               lower.includes('beef') || lower.includes('tofu')) {
      return 'protein';
    } else {
      return 'combination';
    }
  }

  /**
   * Health check
   */
  isReady() {
    return this.modelLoaded;
  }
}

// Singleton instance
const modelService = new ModelService();

module.exports = modelService;
