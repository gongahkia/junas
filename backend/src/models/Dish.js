/**
 * Dish model
 * Stores information about individual cai fan dishes
 * including nutritional data and categorization
 */

const mongoose = require('mongoose');

const DishSchema = new mongoose.Schema({
  name: {
    type: String,
    required: [true, 'Please provide a dish name'],
    unique: true,
    trim: true
  },
  chineseName: {
    type: String,
    trim: true
  },
  category: {
    type: String,
    required: [true, 'Please specify a category'],
    enum: ['vegetable', 'protein', 'starch', 'combination'],
    default: 'combination'
  },
  subcategory: {
    type: String,
    enum: ['chicken', 'pork', 'fish', 'beef', 'tofu', 'egg', 'leafy-green', 'root-vegetable', 'rice', 'noodle', 'mixed', 'seafood', 'mushroom', 'pickled', 'snack']
  },
  description: {
    type: String,
    maxlength: [500, 'Description cannot exceed 500 characters']
  },
  imageUrl: {
    type: String
  },
  
  // Nutritional Information (per 100g serving)
  nutrition: {
    calories: {
      type: Number,
      required: true,
      min: 0
    },
    protein: {
      type: Number, // grams
      required: true,
      min: 0
    },
    carbohydrates: {
      type: Number, // grams
      required: true,
      min: 0
    },
    fat: {
      type: Number, // grams
      required: true,
      min: 0
    },
    fiber: {
      type: Number, // grams
      default: 0,
      min: 0
    },
    sodium: {
      type: Number, // mg
      default: 0,
      min: 0
    }
  },

  // Dish characteristics
  characteristics: {
    isVegetarian: {
      type: Boolean,
      default: false
    },
    isVegan: {
      type: Boolean,
      default: false
    },
    isGlutenFree: {
      type: Boolean,
      default: false
    },
    spicyLevel: {
      type: Number,
      min: 0,
      max: 5,
      default: 0
    }
  },

  // Pricing
  averagePrice: {
    type: Number,
    required: true,
    min: 0
  },

  // Common ingredients for image recognition
  ingredients: [{
    type: String
  }],

  // Visual features for CV recognition
  visualFeatures: {
    dominantColors: [String],
    textureDescription: String
  },

  // Popularity and ratings
  popularityScore: {
    type: Number,
    default: 0,
    min: 0,
    max: 100
  },
  averageRating: {
    type: Number,
    default: 0,
    min: 0,
    max: 5
  },
  ratingCount: {
    type: Number,
    default: 0,
    min: 0
  },

  // Health score (calculated based on nutrition)
  healthScore: {
    type: Number,
    default: 50,
    min: 0,
    max: 100
  },

  createdAt: {
    type: Date,
    default: Date.now
  }
}, {
  timestamps: true
});

// Index for faster searches
DishSchema.index({ name: 'text', chineseName: 'text', category: 1 });

// Calculate health score before saving
DishSchema.pre('save', function(next) {
  // Simple health score calculation
  // Lower calories, higher protein and fiber = better score
  const { calories, protein, fiber, fat, sodium } = this.nutrition;
  
  let score = 50; // Base score
  
  // Adjust for calories (lower is better, within reason)
  if (calories < 100) score += 10;
  else if (calories < 200) score += 5;
  else if (calories > 300) score -= 10;
  
  // Adjust for protein (higher is better)
  if (protein > 15) score += 15;
  else if (protein > 10) score += 10;
  else if (protein > 5) score += 5;
  
  // Adjust for fiber (higher is better)
  if (fiber > 5) score += 10;
  else if (fiber > 3) score += 5;
  
  // Adjust for fat (moderate is best)
  if (fat > 20) score -= 10;
  else if (fat < 5) score += 5;
  
  // Adjust for sodium (lower is better)
  if (sodium > 800) score -= 10;
  else if (sodium < 300) score += 5;
  
  // Bonus for vegetarian/vegan
  if (this.characteristics.isVegan) score += 10;
  else if (this.characteristics.isVegetarian) score += 5;
  
  // Clamp score between 0 and 100
  this.healthScore = Math.max(0, Math.min(100, score));
  
  next();
});

module.exports = mongoose.model('Dish', DishSchema);

