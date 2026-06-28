import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_years(value: str) -> tuple[int, ...]:
    return tuple(int(year.strip()) for year in value.split(",") if year.strip())


@dataclass(frozen=True)
class Settings:
    project_id: str = os.getenv("PROJECT_ID", "undp-project-documents")
    region: str = os.getenv("REGION", "northamerica-northeast1")
    bucket_name: str = os.getenv("BUCKET_NAME", "undp-documents-llm-prod")
    document_ai_location: str = os.getenv("DOCUMENT_AI_LOCATION", "us")
    document_ai_processor_id: str = os.getenv("DOCUMENT_AI_PROCESSOR_ID", "")
    years: tuple[int, ...] = parse_years(
        os.getenv("YEARS", "2023,2024,2025,2026")
    )

    countries: tuple[str, ...] = parse_csv(
        os.getenv(
            "COUNTRIES",
            "Lebanon,Egypt,Iraq,Jordan,Libya,State of Palestine,Syrian Arab Republic,Yemen",
        )
    )

    # Add it here
    document_keywords: tuple[str, ...] = parse_csv(
        os.getenv(
            "DOCUMENT_KEYWORDS",
            "project document,prodoc,amendment",
        )
    )

    max_new_pdfs: int = int(os.getenv("MAX_NEW_PDFS", "100"))

    raw_pdf_prefix: str = os.getenv("RAW_PDF_PREFIX", "raw/pdf")
    pdf_text_prefix: str = os.getenv("PDF_TEXT_PREFIX", "extracted/pdf_text")

    ocr_json_prefix: str = os.getenv("OCR_JSON_PREFIX", "ocr/document_ai_json")
    ocr_text_prefix: str = os.getenv("OCR_TEXT_PREFIX", "ocr/extracted_text")

    combined_text_prefix: str = os.getenv("COMBINED_TEXT_PREFIX", "processed/combined_text")
    chunks_prefix: str = os.getenv("CHUNKS_PREFIX", "processed/chunks")
    embeddings_prefix: str = os.getenv("EMBEDDINGS_PREFIX", "embeddings")

    metadata_prefix: str = os.getenv("METADATA_PREFIX", "metadata")
    logs_prefix: str = os.getenv("LOGS_PREFIX", "logs")

    embedding_model: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
    generation_model: str = os.getenv("GENERATION_MODEL", "gemini-2.5-flash")
    bigquery_dataset: str = os.getenv("BIGQUERY_DATASET","undp_rag_prod",)
    bigquery_table: str = os.getenv("BIGQUERY_TABLE","document_embeddings_prod",)

settings = Settings()