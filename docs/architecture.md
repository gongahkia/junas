# Noupe Architecture

## System Overview

Noupe is a multi-layered Material Non-Public Information (MNPI) classification engine. The system is orchestrated by a FastAPI backend that conditionally loads and executes a sequence of analytical layers in a pipeline to predict sensitivity.

### Key Technologies
- **API & Orchestration:** FastAPI, Uvicorn, Pydantic (Python 3.10+)
- **Lexicon & Rules:** spaCy (NER), Presidio (PII detection), Regular Expressions for financial figures
- **Embeddings:** Sentence-BERT (`all-mpnet-base-v2`) via HuggingFace `sentence-transformers`
- **Machine Learning & NLP Frameworks:** PyTorch, HuggingFace `transformers`
  - FinBERT (binary risk classification over overlapping sliding windows)
  - BERT base uncased (severity classification over overlapping sliding windows)
- **Anomaly Detection:** Scikit-Learn (Isolation Forest for clustering unknown unknowns)
- **State Tracking (Mosaic Layer):** Redis rolling-window event aggregation with per-entity ZSETs and per-event metadata
- **Regression / Final Scoring:** Optional XGBoost layer loaded only when a trained checkpoint is available
- **Interface Surfaces:** Archived HTML/JS demo frontends under `archive/frontend-demos/`, served separately by `scripts/launch/run_dev.sh` and `scripts/launch/run_prod.sh`

### Runtime Layout

- The active runtime is backend-only and is exposed through the compatibility shim `backend.main:app`.
- The canonical stage code now lives under `src/noupe/workflow/`.
- FastAPI no longer mounts chat/email/slack UI routes directly.
- The legacy analyzer plus chat/email/slack demos are static archived demo surfaces that call the backend API over HTTP.
- Swagger and ReDoc are served directly from the FastAPI backend at `/docs` and `/redoc`.

## Data Flow & Pipeline Diagram

The overall pipeline executes a series of sequential and conditional steps upon receiving a text payload.

### Flowchart

```mermaid
flowchart TD
    %% Define Styles
    classDef default fill:#fff,stroke:#333,stroke-width:1px,color:#000;
    classDef io fill:#e0f2fe,stroke:#0284c7,color:#0369a1;
    classDef model fill:#dcfce7,stroke:#16a34a,color:#15803d;
    classDef modelAlt fill:#ecfdf5,stroke:#059669,color:#047857;
    classDef state fill:#fef08a,stroke:#ca8a04,color:#a16207;

    %% Ingestion
    Client([Client Request<br/>JSON Payload]) --> FastAPI[FastAPI Orchestrator]
    class Client io;
    class FastAPI io;

    FastAPI --> Ingestion[Ingestion & Text Prep]

    %% Layer 1
    Ingestion --> L1[Layer 1: Lexicon Check<br/>spaCy / Presidio / Regex]
    class L1 model;

    L1 -- "High Risk Trigger<br/>($ Threshold / Restricted Entity)" --> ShortCircuit[Short-Circuit to High Risk]
    
    %% Proceed if no short circuit
    L1 -- "Clean / Info Match" --> L2[Layer 2: Embeddings Generation<br/>all-mpnet-base-v2]
    class L2 modelAlt;

    %% Flow branches
    L2 --> L3[Layer 3: Clustering<br/>Isolation Forest Anomaly Det.]
    class L3 model;
    
    L2 --> L4[Layer 4: Classification Model 1<br/>FinBERT: Public vs Non-Public]
    class L4 modelAlt;

    %% Conditional Model 2
    L4 -- "Outputs: Risk" --> L4b[Layer 4b: Classification Model 2<br/>BERT: Low vs High Risk]
    class L4b modelAlt;
    L4 -- "Outputs: Safe" --> L5
    
    %% Convergence to Mosaic 
    L3 --> L5[Layer 5: Mosaic Aggregation Logic<br/>Redis Event Aggregator]
    L4b --> L5
    class L5 state;
    
    Redis[(Redis DB)] <--> L5

    L5 -- "Unique fragments >= threshold in window" --> Escalate[Escalate Low->High Risk]

    %% Regression Convergence
    L5 --> Reg[Layer 6: Regression<br/>Feature Weighting]
    class Reg model;
    ShortCircuit --> Reg
    Escalate --> Reg

    %% Final Output
    Reg --> Finalizer[Result Finalizer / JSON Packer]
    Finalizer --> Response([API Response<br/>Layer Details & Final Decision])
    class Response io;
```

### Detailed Data Flow

1. **Ingestion (API Route)**
   A `POST /classify` request carrying a JSON payload (`text`, an optional `entity_id`, and optional flags such as `include_offending_spans`) is received by the FastAPI runtime.
2. **Layer 1: Lexicon Filter**
   The incoming text is processed against regex rules, spaCy Named Entity Recognition, and Microsoft Presidio's PII recognizers. 
   - **Short-Circuit:** If critical elements like restricted entities (from a configuration list) are identified, or high absolute money values are crossed, the flow is instantly flagged `HIGH_RISK`, bypassing the Transformer models.
3. **Layer 2: Embedding Generation**
   The runtime embeds the normalized request text into a dense 768-dimensional vector using the `all-mpnet-base-v2` encoder. Sentence-level embedding generation still exists in the offline training workflow, but inference-time embedding is document-level.
4. **Layer 3: Clustering (Anomaly Detection)**
   An Isolation Forest clustering model ingests the document embedding to compute an anomaly score. This identifies significant divergences against the typical data distribution the models were trained on.
5. **Layer 4 & 4b: Text Classification Models**
   - **Model 1:** The FinBERT checkpoint runs first to act as a primary gate. Inference now uses overlapping token windows so the API can return the top approximate model window without changing the external request shape. If the content is deemed 'public/safe', the second model is skipped.
   - **Model 2:** A severity-checking BERT model evaluates the same sliding-window pattern for text flagged by Model 1, determining if the MNPI risk is `LOW_RISK` or `HIGH_RISK`.
6. **Layer 5: Mosaic Aggregation**
   - Data labeled as `LOW_RISK` proceeds into the Mosaic Tracker. The pipeline connects to a **Redis** instance using the requested `entity_id` (or one inferred from the lexicon).
   - Redis stores a rolling event history for that entity, trims expired events, and deduplicates fragments by normalized fragment hash inside the active time window.
   - If the entity reaches the configured threshold of unique `LOW_RISK` fragments within the active window, the fragmented pieces of context invoke the "Mosaic Theory" and escalate the label to `HIGH_RISK`.
7. **Layer 6: Regression & Final Scoring (Optional)**
   When a trained regression checkpoint exists, scores across upstream models (lexicon score, anomaly float, Transformer risk probabilities, and mosaic unique-fragment counts) are synthesized into an aggregate risk probability.
8. **Response Return**
   The FastAPI structure maps metadata from all layers and encapsulates the final, enumerated decision parameter (`SAFE | LOW_RISK | HIGH_RISK`) into a JSON response. The response can optionally include:
   - per-request observability metadata (`cache_status`, `executed_layers`, `skipped_layers`, `layer_errors`)
   - exact lexicon spans
   - approximate classifier-window spans derived from sliding-window inference
