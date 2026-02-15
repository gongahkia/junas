# Noupe

## Workflow 

* FastAPI orchestration layer for 1-6 (gab)
    * 3 and 4+5 running in parallel 
* *Simple frontend (KIV)*

1. Lexicon (gab)
2. Embeddings (lexuan)
3. Clustering (astin)
4. Classification model 1 (gab, lexuan)
5. Classification model 2 (gab, lexuan)
6. Regression (astin)

## Timeline

* 19 January 2026: Internal check 1 for repo efficacy
* 22 January 2026: Internal check 2 for repo efficacy
* 23 January 2026: Shikhar deadline for first-pass of this repo
* 2 March 2026: Midterm presentation   

## Ingestion schema (for training data)

```json
{
    document_id: UID,
    document_sentence_array: [
        "sentence 1": {
            "text": String,
            "label": String,
        },
        "sentence 2": {
            "text": String,
            "label": String,
        },
        "sentence 3": {
            "text": String,
            "label": String,
        },
        // ... 
    ]
}
```

## Ingestion schema (for test set)

```json
{
    document_creation: DateTime,
    document_id: UID,
    document_name: String,
    document_file_type: String,
    document_num_pages: int,
    document_num_sentences: int,
    document_token_count: int,
    document_permissions: String|null,
    document_raw_text: String,
    document_sentence_array: [
        "sentence 1": {
            "start": int,
            "end": int,
            "text": String,
            "label": String,
        },
        "sentence 2": {
            "start": int,
            "end": int,
            "text": String,
            "label": String,
        },
        "sentence 3": {
            "start": int,
            "end": int,
            "text": String,
            "label": String,
        },
        // ... 
    ],
}
```

## Output schema (for test set)

```json
{
    // backend metadat
    transaction_id: UID,

    // document metadata
    document_creation: DateTime,
    document_id: UID,
    document_name: String,
    document_file_type: String,
    document_num_pages: int,
    document_num_sentences: int,
    document_token_count: int,
    document_permissions: String|null,
    document_id: UID,

    // layer 1
    document_lexicon_check: Boolean,
    document_lexicon_blacklist: Null|[String],

    // layer 2
    document_clustering_anomaly_check: Boolean,
    document_clustering_anomalous_cluster_score: Null|Double,
    document_clustering_path_length: Int,

    // layer 3
    document_classification_model_1_check: Boolean,
    document_classification_model_1_classification_score: Double,

    // layer 4
    document_classification_model_2_check: Boolean,
    document_classification_model_2_classification_score: Double,

    // layer 5
    document_mosiac_aggregation_check: Boolean,
    document_mosiac_aggregation_score: Null|Double,

    // layer 6
    document_risk_probability: Double,
    document_feature_importance_tree: [feature_1, feature_2, feature_3],

    document_sentence_array: [
        "sentence 1": {
            "start": int,
            "end": int,
            "text": String,
            "label": String,
        },
        "sentence 2": {
            "start": int,
            "end": int,
            "text": String,
            "label": String,
        },
        "sentence 3": {
            "start": int,
            "end": int,
            "text": String,
            "label": String,
        },
        // ... 
    ]
}
```