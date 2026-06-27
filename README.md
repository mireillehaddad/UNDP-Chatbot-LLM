

Open UNDP API
        │
        ▼
Download PDF
        │
        ▼
raw/pdf/
        │
        ▼
Text Extraction
        │
        ├── Try PyPDF extraction
        │
        ├── If text is sufficient
        │       ▼
        │   processed/combined_text/
        │
        └── Otherwise
                ▼
         Document AI OCR
                │
                ├── ocr/document_ai_json/
                ├── ocr/extracted_text/
                └── processed/combined_text/
                        │
                        ▼
                Chunking Pipeline
                        │
                        ▼
                processed/chunks/
                        │
                        ▼
                Embedding Pipeline
                        │
                        ▼
                   embeddings/
                        │
                        ▼
            Retrieval + Gemini Chatbot

## Step 1

```
gcloud storage buckets create gs://undp-documents-llm-prod `
  --location=northamerica-northeast1 `
  --uniform-bucket-level-access
  ```


## Step 2

Create the new folder structure

```
"" | gcloud storage cp - gs://undp-documents-llm-prod/raw/pdf/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/extracted/pdf_text/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/ocr/document_ai_json/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/ocr/extracted_text/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/processed/combined_text/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/processed/chunks/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/embeddings/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/metadata/.keep
"" | gcloud storage cp - gs://undp-documents-llm-prod/logs/.keep
```

## Step 3

Create the local project structure

UNDP-Chatbot-LLM/
│
├── src/
│   ├── common/
│   ├── ingest/
│   ├── extract/
│   ├── ocr/
│   ├── combine/
│   ├── chunk/
│   ├── embed/
│   ├── retrieval/
│   └── chatbot/
│
├── docker/
│
├── workflows/
│
├── scheduler/
│
├── tests/
│
├── docs/
│
├── scripts/
│
├── .env.example
├── pyproject.toml
├── uv.lock
├── cloudbuild.yaml
├── README.md
└── .gitignore

```


mkdir src

mkdir src\common
mkdir src\ingest
mkdir src\extract
mkdir src\ocr
mkdir src\combine
mkdir src\chunk
mkdir src\embed
mkdir src\retrieval
mkdir src\chatbot

mkdir docker
mkdir workflows
mkdir scheduler
mkdir docs
mkdir scripts
mkdir tests

```
##
Create the Python packages
```
New-Item src\common\settings.py -ItemType File
New-Item src\common\gcs_utils.py -ItemType File

New-Item src\ingest\run_ingest.py -ItemType File

New-Item src\extract\run_pdf_text.py -ItemType File

New-Item src\ocr\run_ocr.py -ItemType File

New-Item src\combine\run_combine.py -ItemType File

New-Item src\chunk\run_chunk.py -ItemType File

New-Item src\embed\run_embed.py -ItemType File

New-Item src\retrieval\retriever.py -ItemType File

New-Item src\chatbot\qa.py -ItemType File
New-Item src\chatbot\app.py -ItemType File
```

Now create the deployment files:

```
New-Item docker\Dockerfile.ingest -ItemType File
New-Item docker\Dockerfile.extract -ItemType File
New-Item docker\Dockerfile.ocr -ItemType File
New-Item docker\Dockerfile.combine -ItemType File
New-Item docker\Dockerfile.chunk -ItemType File
New-Item docker\Dockerfile.embed -ItemType File
New-Item docker\Dockerfile.chatbot -ItemType File

New-Item workflows\undp_pipeline_workflow.yaml -ItemType File

New-Item scheduler\create_weekly_schedule.md -ItemType File

New-Item cloudbuild.yaml -ItemType File

```

## 
Create these files :


.env.example

##
Create 

.gitignore


##
Initializa project

```
uv init

```

##
Then create the virtual environment:
```
uv venv

```
Activate it:

```
.venv\Scripts\Activate.ps1
```

## Install the dependencies
```
uv add `
requests `
google-cloud-storage `
google-cloud-documentai `
google-genai `
google-cloud-aiplatform `
python-dotenv `
pypdf `
numpy `
pandas `
streamlit
```

## Generate the lock file:
```
uv lock

```

                   PDF
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     PyPDF Extraction    Document AI OCR
          │                   │
          ▼                   ▼
   extracted/pdf_text   ocr/extracted_text
          │                   │
          └─────────┬─────────┘
                    ▼
          Text Combination & Validation
                    ▼
       processed/combined_text
                    ▼
              Chunking
                    ▼
             Embeddings
                    ▼
              Vector Search
                    ▼
             Gemini Chatbot


## add this
raw/pdf
   ├── PyPDF extraction → extracted/pdf_text
   └── OCR extraction   → ocr/extracted_text
                         ↓
                  merge/combine step
                         ↓
              processed/combined_text
                         ↓
                    chunk → embed
```
New-Item src\combine\run_combine.py -ItemType File -Force
```

## Build the configuration layer

```
src/common/settings.py
src/common/gcs_utils.py

```

Test configuration
```
python -c "from src.common.settings import settings; print(settings)"

```


## Next we build: 
src/ingest/run_ingest.py

```
python -m src.ingest.run_ingest

```


Ingestion complete.
Uploaded new PDFs: 78
Skipped existing PDFs: 19

PDF inventory.
Total PDF files in bucket: 97
Unique document IDs: 42
Unique project IDs: 20
(UNDP-Chatbot-LLM) PS C:\Users\mirei\Desktop\UNDP-Chatbot-LLM> 


## Future Retrieval Improvements

After the OCR pipeline is working, improve retrieval by adding:

- In-memory vector search for faster local retrieval
- Keyword/BM25 search for exact terms, names, and project IDs
- Hybrid search using Reciprocal Rank Fusion (RRF)
- Optional migration later to Vertex AI Vector Search or another vector database


## Build src/extract/run_extract_text.py.


For each PDF

1. Read the manifest
2. Download the PDF
3. Try PyPDF extraction
4. If enough text:
      save to processed/combined_text/
      update manifest
5. Otherwise:
      run Document AI OCR
      save OCR JSON
      save OCR text
      save final text to processed/combined_text/
      update manifest

### New chatbot is  document-oriented:

PDF
↓
Manifest
↓
Extraction
↓
Chunking
↓
Embeddings

Verify output in GCS
```
gcloud storage ls gs://undp-documents-llm-prod/processed/combined_text/ --recursive
```


To add Document AI OCR fallback inside run_extract_text.py. 
Before coding OCR, create a Document AI OCR processor and get these 3 values: how to do this add Document AI OCR fallback inside run_extract_text.py. Before coding OCR, create a Document AI OCR processor

### Enable Document AI API

```
gcloud services enable documentai.googleapis.com
```

![
](image.png)


Open Document AI

Go to Google Cloud Console.

Search:

Document AI

Then open:

Document AI → Processor Gallery

Google’s docs say processors must be created before you can process documents, and OCR is one of the available processor types.

Step 3 — Choose OCR processor

In the Processor Gallery, search:

OCR

Choose:

OCR Processor

or:

Enterprise Document OCR

For your project, choose OCR Processor first.

Step 4 — Create processor

Click:

Create processor

Fill:

Name: undp-ocr-processor
Region: us

Then click:

Create

Google’s creation flow asks you to choose the processor type, give it a name, select a region, then create it.

Step 5 — Copy the processor ID

After creation, you will be taken to the processor Overview page.

You should see:

Processor ID
Location
Prediction endpoint



https://us-documentai.googleapis.com/v1/projects/1097805338474/locations/us/processors/a13faf394c2fce1:process


.env.example

Add:

DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_PROCESSOR_ID=a13faf394c2fce1

## REMARK
Why this happens

Document AI synchronous OCR is not ideal for long PDFs. Later, for full documents, use batch processing from GCS input to GCS output.

For now, limiting pages lets you test OCR fallback and continue building the pipeline.


## Add chunking 

Add chunking step:

src/chunk/run_chunk.py