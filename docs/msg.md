Hi @meryldany @keibtang tech team will need your help over this week to generate 

- 1 batch JSON containing multiple synthetic "documents" that follows the below format
- total 32 synthetic "document" entries inside the batch
    - 30 normal documents
    - 2 anomalous documents

normal JSON documents

- each document has 20 sentences + labels on financial data/documents an investment bank or financial sector employee would have
- each label can only be one of these three canonical values (`"high"`, `"low"`, `"non"`)
- for each normal synthetic "document"
    - can ask AI to produce 30% high, 30% low, 40% non-sensitive sentences and label accordingly
    - can ask AI to put people names (eg. John) or monetary values (eg. $5,000,000 trade)
- below is the exact batch JSON schema we need, so can feed it alongside ur prompt to the LLM

```json
{
    batch_name: String,
    batch_creation: DateTime,
    documents: [
        {
            document_id: UID,
            document_sentence_array: [
                "sentence 1": {
                    "text": String,
                    "label": String
                },
                "sentence 2": {
                    "text": String,
                    "label": String
                },
                "sentence 3": {
                    "text": String,
                    "label": String
                }
                // ...
            ]
        }
    ]
}
```

anomalous JSON documents

- each of these 2 anomalous documents has 20 sentences + labels on financial data/documents an investment bank or financial sector employee would have
- each label can only be one of these three canonical values (`"high"`, `"low"`, `"non"`)
- for each anomalous synthetic "document"
    - can ask AI to make the phrasing/vocabulary/semantic/situation within the document as anomalous as possible from the other 30 normal documents (eg. commiting tax fraud, leaked executive memo for unannounced strategic pivot)
    - can ask AI to produce 30% high, 30% low, 40% non-sensitive sentences and label accordingly
    - can ask AI to put people names (eg. John) or monetary values (eg. $5,000,000 trade)
- below is the exact batch JSON schema we need, so can feed it alongside ur prompt to the LLM

```json
{
    batch_name: String,
    batch_creation: DateTime,
    documents: [
        {
            document_id: UID,
            document_sentence_array: [
                "sentence 1": {
                    "text": String,
                    "label": String
                },
                "sentence 2": {
                    "text": String,
                    "label": String
                },
                "sentence 3": {
                    "text": String,
                    "label": String
                }
                // ...
            ]
        }
    ]
}
```
