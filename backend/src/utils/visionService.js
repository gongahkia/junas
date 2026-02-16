/**
 * Computer Vision Service
 * Handles dish recognition using trained neural network.
 * Requires a trained ONNX model — will not run without one.
 */

const modelService = require('./modelService');

class VisionService {
  constructor() {
    this.modelLoaded = false;
  }

  async initialize() {
    const modelReady = await modelService.initialize();
    if (!modelReady) {
      console.error('❌ No trained model found. Train one first: cd training && python train_tui.py');
    }
    this.modelLoaded = modelReady;
  }

  async analyzeDish(imagePath) {
    if (!this.modelLoaded) {
      await this.initialize();
    }
    if (!this.modelLoaded) {
      throw new Error('No trained model available. Train a model first with: cd training && python train_tui.py');
    }
    return await modelService.analyzeDish(imagePath);
  }

  isReady() {
    return this.modelLoaded;
  }
}

const visionService = new VisionService();
module.exports = visionService;
