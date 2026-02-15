[![](https://img.shields.io/badge/caipng_1.0.0-passing-%23004D00)](https://github.com/gongahkia/caipng/releases/tag/1.0.0)
[![](https://img.shields.io/badge/caipng_2.0.0-passing-%23228B22)](https://github.com/gongahkia/caipng/releases/tag/2.0.0)
[![](https://img.shields.io/badge/caipng_3.0.0-passing-%2332CD32)](https://github.com/gongahkia/caipng/releases/tag/3.0.0)

# `cAI-png`

[Cai Fan](https://en.wikipedia.org/wiki/Economy_rice) [Macros](https://www.calculator.net/macro-calculator.html) Estimation Web App, [built](#architecture) atop a [Computer Vision](https://www.ibm.com/think/topics/computer-vision) Engine.

Available [backend endpoints](#architecture) are [here](#api-reference).

<div align="center">
  <img src="./asset/logo/caifan.jpg" width="65%">
</div>

## Stack

* Frontend: [React](https://react.dev), [Vite](https://vitejs.dev) 
* Backend: [Node.js](https://nodejs.org), [Express.js](https://expressjs.com), [Mongoose](https://mongoosejs.com)
* Database: [MongoDB](https://www.mongodb.com) 
* Computer Vision: [Sharp](https://sharp.pixelplumbing.com) 
* LLM: [Gemini](https://ai.google.dev) 
* Package: [Docker](https://www.docker.com), [Docker Compose](https://docs.docker.com/compose/)

## Usage

The below instructions are for locally hosting `cAI-png`.

1. First execute the below.

```console
$ git clone https://github.com/gongahkia/caipng.git && cd caipng
```

2. Set up MongoDB [locally](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/) or via [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).

3. Create and fill up `backend/.env`.

```env
NODE_ENV=development
PORT=5000
MONGODB_URI=mongodb://localhost:27017/caipng
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
MAX_FILE_SIZE=10485760
UPLOAD_PATH=./uploads
CORS_ORIGIN=http://localhost:3000
```

4. Create and fill up `frontend/.env`.

```env
VITE_API_URL=http://localhost:5000/api
VITE_MAX_IMAGE_SIZE=10485760
```

4. Install dependencies and seed database:

```console
$ cd backend && npm install
$ npm run seed
$ cd ../frontend && npm install
$ cd ..
```

5. Run with Docker Compose or the Makefile.

```console
$ docker-compose up -d
$ docker-compose exec backend npm run seed
$ make install
$ make docker-up
```

* Frontend: http://localhost:3000
* Backend API: http://localhost:5000
* Health Check: http://localhost:5000/health

## Screenshot

![](./asset/reference/1.png)

## Architecture

* Browser captures frames
* Backend runs heuristic detection and returns bounding boxes with confidences at ~5–10 FPS
* Derived text summary is sent to Gemini to estimate macros
* No images are sent to the LLM

### System Context Diagram

```mermaid
C4Context
    title System Context Diagram for cAI-png

    Person(user, "User", "Uploads cai fan images and receives personalized meal recommendations")

  System(web_app, "cAI-png Web Application", "React SPA with live webcam overlay")
  System(backend_api, "Backend API", "Express.js server handling live frame analysis and LLM macros")
  System(database, "MongoDB Database", "Stores dish reference data only")
    
  System_Ext(image_processor, "Image Processing", "Sharp-based feature extraction")
  System_Ext(vision_service, "Vision Service", "Heuristic matching for dish/categories")
  System_Ext(llm, "Gemini LLM", "Text-only macro estimation")

    Rel(user, web_app, "Uploads images, sets preferences", "HTTPS")
    Rel(web_app, backend_api, "Makes API calls", "REST API")
    Rel(backend_api, database, "Queries and stores data", "MongoDB Protocol")
    Rel(backend_api, image_processor, "Processes uploaded images", "Library")
  Rel(backend_api, vision_service, "Analyzes frames")
  Rel(backend_api, llm, "Text prompt with derived detections")
```

### Container Diagram

```mermaid
C4Container
    title Container Diagram for cAI-png

    Person(user, "User")

    Container_Boundary(caipng_system, "cAI-png System") {
  Container(react_app, "React Frontend", "React 18, Vite", "Single live page with webcam and overlay")
  Container(express_api, "Express Backend", "Node.js, Express", "REST API for live analyze + macros")
  Container(vision_service, "Vision Service", "Sharp heuristics", "Frame analysis with boxes/confidences")
  ContainerDb(mongodb, "MongoDB", "NoSQL Database", "Stores dish reference data")
    }

    Rel(user, react_app, "Interacts with", "HTTPS")
    Rel(react_app, express_api, "API calls", "REST/JSON")
    Rel(express_api, vision_service, "Analyzes images")
  Rel(express_api, mongodb, "Reads dish data", "Mongoose ODM")
  Rel(vision_service, mongodb, "Fetches dish features", "Mongoose ODM")
```

### Live Analysis Flow

```mermaid
C4Component
    title Image Analysis Component Flow

  Person(user, "User", "Holds plate in front of webcam")

    Container_Boundary(backend_system, "Backend System") {
  Component(live_controller, "Live Controller", "Express.js", "Accepts frames, returns boxes+confidences")
  Component(image_processor, "Image Processor", "Sharp", "Extracts features")
  Component(vision_service, "Vision Service", "Heuristics", "Identifies likely dishes/categories")
    }

    Container_Boundary(data_layer, "Data Layer") {
        ComponentDb(mongodb, "MongoDB", "Database", "Dish library with visual features")
        ComponentDb(uploads_storage, "File Storage", "Disk", "Uploaded images")
    }

  Rel(user, live_controller, "POST /api/live/analyze (base64 frame)", "JSON")
  Rel(live_controller, image_processor, "Extract features")
  Rel(image_processor, uploads_storage, "Temp files (optional)")
  Rel(live_controller, vision_service, "Analyze frame")
  Rel(live_controller, user, "Return boxes + confidences", "JSON")
```

### Macros Estimation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as Express API
    participant Pref as Preference Store
    participant Rec as Recommendation Engine
    participant DB as Dish Database

  participant U as User
  participant API as Express API
  participant LLM as Gemini

  U->>API: POST /api/live/macros (derived text: labels + avg confidences)
  API->>LLM: Prompt with derived text (no images)
  LLM->>API: JSON with macros + narrative
  API->>U: Return macros summary
```

### Data Model

```mermaid
erDiagram
    USERS ||--o{ PREFERENCES : has
    USERS ||--o{ FAVORITES : has
    USERS ||--o{ ANALYSES : creates
    DISHES ||--o{ FAVORITES : "in"
    DISHES ||--o{ ANALYSIS_DISHES : "identified in"
    ANALYSES ||--o{ ANALYSIS_DISHES : contains
    
    USERS {
        ObjectId _id PK
        string name
        string email UK
        string password "bcrypt hashed"
        array favoriteDishes "Array of Dish IDs"
        timestamp createdAt
        timestamp updatedAt
    }
    
    DISHES {
        ObjectId _id PK
        string name
        string chineseName
        enum category "vegetable, protein, starch, combination"
        string subcategory
        string description
        object nutrition "calories, protein, carbs, fat, fiber, sodium"
        object characteristics "vegetarian, vegan, glutenFree, spicy"
        decimal averagePrice
        array ingredients
        object visualFeatures "dominantColors, textureDescription"
        int healthScore
        int popularityScore
        timestamp createdAt
    }
    
    PREFERENCES {
        ObjectId _id PK
        ObjectId userId FK
        object dietaryRestrictions "vegetarian, vegan, glutenFree, halal"
        object nutritionalGoals "goalType, targets"
        object budgetPreferences "maxPricePerMeal, preferBudgetOptions"
        object tastePreferences "maxSpicyLevel, dislikedIngredients"
        object healthPriorities "prioritizeHighProtein, prioritizeLowCalorie"
        object mealComposition "preferredVegetableCount, preferredProteinCount"
        timestamp createdAt
        timestamp updatedAt
    }
    
    ANALYSES {
        ObjectId _id PK
        ObjectId userId FK "optional"
        string imageUrl
        array identifiedDishes "Array of identified dish objects"
        object nutritionalSummary "totals"
        object metadata "processingTime, modelVersion"
        enum status "completed, failed, processing"
        timestamp createdAt
    }
```

## API Reference

### Base URL
- **Development**: `http://localhost:5000`
- **Production**: `https://api.caipng.example.com`

### Endpoints

#### Health Check
```http
GET /health
```

**Response**:
```json
{
  "success": true,
  "message": "cAI-png server is running",
  "timestamp": "2024-01-01T12:00:00.000Z"
}
```

#### Live Analyze Frame
```http
POST /api/live/analyze
Content-Type: application/json

{
  "imageBase64": "data:image/jpeg;base64,..."
}
```

Response:
```json
{
  "success": true,
  "detections": [
    { "label": "vegetable", "confidence": 0.76, "box": { "x": 100, "y": 60, "width": 180, "height": 140 } }
  ]
}
```

#### Estimate Macros (LLM)
```http
POST /api/live/macros
Content-Type: application/json

{
  "derivedText": "Detected items (rolling):\nvegetable: avgConfidence=78%\nprotein: avgConfidence=65%\n"
}
```

Response:
```json
{
  "success": true,
  "macros": { "calories": 640, "protein": 28, "carbs": 70, "fat": 20 },
  "narrative": "Estimated based on detected categories and common portions."
}
```
