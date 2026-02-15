/**
 * LLM Service (Gemini Free)
 * Calls Google Gemini with derived text (no image data) to estimate macros
 */

const Dish = require('../models/Dish');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const MODEL = process.env.GEMINI_MODEL || 'gemini-1.5-flash';

if (!global.fetch) {
  // Node 18+ has fetch; fallback not implemented intentionally
}

async function getDishNutritionContext() {
  try {
    const dishes = await Dish.find({}, 'name category nutrition').lean().maxTimeMS(2000);
    if (!dishes.length) return '';
    const lines = dishes.map(d =>
      `${d.name} (${d.category}): ${d.nutrition.calories}kcal, ${d.nutrition.protein}g protein, ${d.nutrition.carbohydrates}g carbs, ${d.nutrition.fat}g fat per 100g`
    );
    return `\nReference dish nutrition (per 100g):\n${lines.join('\n')}\n`;
  } catch (_) {
    return '';
  }
}

const buildPrompt = (derivedText, dishContext) => `You are a nutrition assistant. From the following structured description of a cai fan meal, estimate total macros for the plate.
Anchor your estimates to the reference nutrition data provided below when dish names match detected categories.
Return concise JSON with fields: calories (kcal), protein (g), carbs (g), fat (g) and a brief narrative field. Be conservative.
${dishContext}
Description:\n${derivedText}

Output JSON only, like: {"calories": 650, "protein": 28, "carbs": 75, "fat": 22, "narrative": "..."}`;

async function callGeminiForMacros(derivedText) {
  if (!GEMINI_API_KEY) {
    return {
      macros: { calories: 0, protein: 0, carbs: 0, fat: 0 },
      narrative: 'Gemini API key not set; returning placeholder values.'
    };
  }

  const dishContext = await getDishNutritionContext();
  const prompt = buildPrompt(derivedText, dishContext);

  // Google AI Studio Generative Language API endpoint
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${GEMINI_API_KEY}`;

  const body = {
    contents: [
      {
        parts: [{ text: prompt }]
      }
    ]
  };

  // Retry once with exponential backoff for transient failures
  let resp;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (resp.ok || resp.status < 500) break;
    } catch (fetchErr) {
      if (attempt === 1) {
        return {
          macros: { calories: 0, protein: 0, carbs: 0, fat: 0 },
          narrative: `Gemini API fetch error: ${fetchErr.message}`
        };
      }
    }
    if (attempt === 0) await new Promise(r => setTimeout(r, 1000));
  }

  if (!resp.ok) {
    return {
      macros: { calories: 0, protein: 0, carbs: 0, fat: 0 },
      narrative: `Gemini API error: ${resp.status}`
    };
  }

  const data = await resp.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';

  try {
    const parsed = JSON.parse(text.trim());
    const macros = {
      calories: Number(parsed.calories) || 0,
      protein: Number(parsed.protein) || 0,
      carbs: Number(parsed.carbs) || 0,
      fat: Number(parsed.fat) || 0,
    };
    const narrative = parsed.narrative || 'Estimated macros.';
    return { macros, narrative };
  } catch (_) {
    // If not valid JSON, return the text as narrative
    return {
      macros: { calories: 0, protein: 0, carbs: 0, fat: 0 },
      narrative: text || 'Unable to parse LLM response.'
    };
  }
}

module.exports = { callGeminiForMacros };
