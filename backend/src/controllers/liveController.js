/**
 * Live Controller (V2)
 * - analyzeFrame: accepts base64 image data, runs heuristic analysis and returns boxes/labels/confidence
 * - estimateMacros: accepts derived text (no images), calls Gemini and returns macros
 */

const path = require('path');
const fs = require('fs');
const { v4: uuidv4 } = require('uuid');
const visionService = require('../utils/visionService');
const { callGeminiForMacros } = require('../utils/llmService');

// Ensure temp dir exists
const tmpDir = path.join(__dirname, '../../uploads/tmp');
if (!fs.existsSync(tmpDir)) {
  fs.mkdirSync(tmpDir, { recursive: true });
}

/**
 * POST /api/live/analyze
 * body: { imageBase64: string } // data URL or raw base64
 */
exports.analyzeFrame = async (req, res, next) => {
  try {
    const { imageBase64 } = req.body || {};

    if (!imageBase64) {
      return res.status(400).json({ success: false, message: 'imageBase64 is required' });
    }

    // Strip data URL prefix if present
    const base64Data = imageBase64.replace(/^data:image\/[a-zA-Z]+;base64,/, '');
    const filename = `${uuidv4()}.jpg`;
    const filePath = path.join(tmpDir, filename);

    fs.writeFileSync(filePath, Buffer.from(base64Data, 'base64'));

    try {
      const analysis = await visionService.analyzeDish(filePath);

      // Shape detections to simple structure
      const detections = (analysis.identifiedDishes || []).map((d) => ({
        label: d.dishName || d.category,
        dishId: d.dish || null,
        confidence: d.confidence,
        box: d.boundingBox,
        category: d.category,
      }));

      return res.status(200).json({
        success: true,
        fpsHint: 5,
        detections,
      });
    } finally {
      // Clean up temp file
      try { fs.unlinkSync(filePath); } catch (_) {}
    }
  } catch (err) {
    next(err);
  }
};

/**
 * POST /api/live/macros
 * body: { derivedText: string }
 * Returns: { macros: { calories, protein, carbs, fat }, narrative }
 */
exports.estimateMacros = async (req, res, next) => {
  try {
    let { derivedText } = req.body || {};
    if (!derivedText) {
      return res.status(400).json({ success: false, message: 'derivedText is required' });
    }

    // Sanitize: strip non-printable chars (keep newlines/tabs), cap at 2000 chars
    derivedText = derivedText.replace(/[^\x20-\x7E\n\t]/g, '').slice(0, 2000);

    const result = await callGeminiForMacros(derivedText);
    return res.status(200).json({ success: true, ...result });
  } catch (err) {
    next(err);
  }
};
