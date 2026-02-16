/**
 * Neural Network Model Service
 * Handles ONNX model inference for food recognition
 * Includes inference cache (SHA256-keyed) and abstention logic
 */

const ort = require('onnxruntime-node');
const sharp = require('sharp');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');

const MODEL_PATH = path.join(__dirname, '../../models/caifan_model.onnx');
const CLASSES_PATH = path.join(__dirname, '../../models/classes.json');

const MEAN = [0.485, 0.456, 0.406];
const STD = [0.229, 0.224, 0.225];
const IMAGE_SIZE = 224;

// abstention thresholds (adapted from uh-kun scoring.py)
const MIN_CONFIDENCE = 0.15; // min top-1 probability to accept
const MARGIN_THRESHOLD = 0.08; // min gap between top-1 and top-2
const MAX_CACHE_SIZE = 200;
const CACHE_TTL_MS = 30000; // 30s ttl per entry

class InferenceCache {
  constructor(maxSize = MAX_CACHE_SIZE, ttlMs = CACHE_TTL_MS) {
    this.maxSize = maxSize;
    this.ttlMs = ttlMs;
    this.cache = new Map(); // sha256 -> {result, ts}
  }
  _hash(buffer) {
    return crypto.createHash('sha256').update(buffer).digest('hex');
  }
  get(buffer) {
    const key = this._hash(buffer);
    const entry = this.cache.get(key);
    if (!entry) return null;
    if (Date.now() - entry.ts > this.ttlMs) {
      this.cache.delete(key);
      return null;
    }
    return entry.result;
  }
  set(buffer, result) {
    const key = this._hash(buffer);
    if (this.cache.size >= this.maxSize) { // evict oldest
      const oldest = this.cache.keys().next().value;
      this.cache.delete(oldest);
    }
    this.cache.set(key, { result, ts: Date.now() });
  }
  get size() { return this.cache.size; }
}

class ModelService {
  constructor() {
    this.session = null;
    this.classes = null;
    this.modelLoaded = false;
    this.inferenceCache = new InferenceCache();
  }

  async initialize() {
    try {
      if (!fs.existsSync(MODEL_PATH)) {
        console.warn('⚠️  Model file not found. Using fallback mode.');
        console.warn(`   Expected model at: ${MODEL_PATH}`);
        console.warn('   Tip: Train the model first using training/train_tui.py');
        this.modelLoaded = false;
        return false;
      }
      if (!fs.existsSync(CLASSES_PATH)) {
        console.warn('⚠️  Classes file not found. Using fallback mode.');
        console.warn(`   Expected classes at: ${CLASSES_PATH}`);
        this.modelLoaded = false;
        return false;
      }
      const classesData = fs.readFileSync(CLASSES_PATH, 'utf8');
      this.classes = JSON.parse(classesData);
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

  async preprocessImage(imagePath) {
    try {
      const imageBuffer = await sharp(imagePath)
        .resize(IMAGE_SIZE, IMAGE_SIZE)
        .removeAlpha()
        .raw()
        .toBuffer();
      const float32Data = new Float32Array(3 * IMAGE_SIZE * IMAGE_SIZE);
      const pixels = new Uint8Array(imageBuffer);
      for (let c = 0; c < 3; c++) {
        for (let h = 0; h < IMAGE_SIZE; h++) {
          for (let w = 0; w < IMAGE_SIZE; w++) {
            const pixelIdx = (h * IMAGE_SIZE + w) * 3 + c;
            const tensorIdx = c * IMAGE_SIZE * IMAGE_SIZE + h * IMAGE_SIZE + w;
            float32Data[tensorIdx] = (pixels[pixelIdx] / 255.0 - MEAN[c]) / STD[c];
          }
        }
      }
      return { float32Data, imageBuffer };
    } catch (error) {
      console.error('Error preprocessing image:', error);
      throw error;
    }
  }

  /**
   * Apply abstention logic to predictions.
   * Rejects if top-1 confidence < MIN_CONFIDENCE or margin to top-2 < MARGIN_THRESHOLD.
   */
  applyAbstention(predictions) {
    if (!predictions || predictions.length === 0) return [];
    const top = predictions[0];
    if (top.confidence < MIN_CONFIDENCE) {
      return predictions.map(p => ({ ...p, abstained: true }));
    }
    if (predictions.length >= 2) {
      const margin = top.confidence - predictions[1].confidence;
      if (margin < MARGIN_THRESHOLD) {
        return predictions.map(p => ({ ...p, abstained: true }));
      }
    }
    return predictions.map((p, i) => ({ ...p, abstained: false }));
  }

  async predict(imagePath) {
    if (!this.modelLoaded) {
      throw new Error('Model not loaded. Please initialize first.');
    }
    try {
      const startTime = Date.now();
      const { float32Data, imageBuffer } = await this.preprocessImage(imagePath);

      // check cache
      const cached = this.inferenceCache.get(imageBuffer);
      if (cached) {
        return { ...cached, processingTime: Date.now() - startTime, cacheHit: true };
      }

      const tensor = new ort.Tensor('float32', float32Data, [1, 3, IMAGE_SIZE, IMAGE_SIZE]);
      const feeds = { input: tensor };
      const results = await this.session.run(feeds);
      const output = results.output.data;

      const maxLogit = Math.max(...Array.from(output));
      const expScores = Array.from(output).map(x => Math.exp(x - maxLogit));
      const sumExp = expScores.reduce((a, b) => a + b, 0);
      const probabilities = expScores.map(x => x / sumExp);

      let predictions = probabilities
        .map((prob, idx) => ({
          classId: idx,
          className: this.classes[idx] || `class_${idx}`,
          confidence: prob
        }))
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 5);

      // apply abstention
      predictions = this.applyAbstention(predictions);

      const processingTime = Date.now() - startTime;
      const result = { predictions, processingTime, modelVersion: 'neural-v1.1' };

      // cache result
      this.inferenceCache.set(imageBuffer, { predictions, modelVersion: 'neural-v1.1' });

      return { ...result, cacheHit: false };
    } catch (error) {
      console.error('Error during inference:', error);
      throw error;
    }
  }

  async analyzeDish(imagePath) {
    if (!this.modelLoaded) {
      throw new Error('Model not loaded. Cannot analyze dish.');
    }
    try {
      const startTime = Date.now();
      const metadata = await sharp(imagePath).metadata();
      const { width, height } = metadata;
      const result = await this.predict(imagePath);

      const identifiedDishes = result.predictions
        .filter(p => !p.abstained && p.confidence > 0.1)
        .map((pred, idx) => {
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
            boundingBox: { x: col * boxW, y: row * boxH, width: boxW, height: boxH }
          };
        });

      const processingTime = Date.now() - startTime;
      return {
        identifiedDishes,
        processingTime,
        imageFeatures: {
          dimensions: { width, height },
          modelVersion: 'neural-v1.1',
          cacheHit: result.cacheHit || false,
          cacheSize: this.inferenceCache.size
        }
      };
    } catch (error) {
      console.error('Error analyzing dish:', error);
      throw error;
    }
  }

  inferCategory(className) {
    const lower = className.toLowerCase();
    if (lower.includes('rice') || lower.includes('noodle') || lower.includes('bread') || lower.includes('bee_hoon') || lower.includes('mee')) return 'starch';
    if (lower.includes('vegetable') || lower.includes('salad') || lower.includes('green') || lower.includes('bean') || lower.includes('kangkung') || lower.includes('broccoli') || lower.includes('cabbage') || lower.includes('spinach') || lower.includes('chye') || lower.includes('bok')) return 'vegetable';
    if (lower.includes('chicken') || lower.includes('fish') || lower.includes('meat') || lower.includes('pork') || lower.includes('beef') || lower.includes('tofu') || lower.includes('egg') || lower.includes('prawn') || lower.includes('shrimp') || lower.includes('otah') || lower.includes('char_siew')) return 'protein';
    return 'combination';
  }

  isReady() {
    return this.modelLoaded;
  }
}

const modelService = new ModelService();
module.exports = modelService;
