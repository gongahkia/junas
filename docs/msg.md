Hi @meryldany @keibtang tech team will need your help over this week to generate 

- 1 JSON = 1 synthetic "document" that follows the below format
- total 32 JSON (ie. 32 pieces of synthetic "document")
    - 30 normal JSON documents
    - 2 anomalous JSON documents

normal JSON documents

- each JSON has 20 sentences + labels on financial data/documents an investment bank or financial sector employee would have
- each label can only be one of these three canonical values (`"high"`, `"low"`, `"non"`)
- for each normal JSON synthetic "document"
    - can ask AI to produce 30% high, 30% low, 40% non-sensitive sentences and label accordingly
    - can ask AI to put people names (eg. John) or monetary values (eg. $5,000,000 trade)
- below is the exact JSON schema we need, so can feed it alongside ur prompt to the LLM

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

anomalous JSON documents

- each of these 2 JSON have 20 sentences + labels on financial data/documents an investment bank or financial sector employee would have
- each label can only be one of these three canonical values (`"high"`, `"low"`, `"non"`)
- for each anomalous JSON synthetic "document"
    - can ask AI to make the phrasing/vocabulary/semantic/situation within the document as anomalous as possible from the other 30 normal documents (eg. commiting tax fraud, leaked executive memo for unannounced strategic pivot)
    - can ask AI to produce 30% high, 30% low, 40% non-sensitive sentences and label accordingly
    - can ask AI to put people names (eg. John) or monetary values (eg. $5,000,000 trade)
- below is the exact JSON schema we need, so can feed it alongside ur prompt to the LLM

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
