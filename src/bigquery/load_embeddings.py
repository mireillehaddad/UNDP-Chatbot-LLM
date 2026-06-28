import json
from datetime import datetime, timezone

from google.cloud import bigquery

from src.common.gcs_utils import download_text, list_blobs
from src.common.settings import settings


BATCH_SIZE = 500


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def table_id() -> str:
    return (
        f"{settings.project_id}."
        f"{settings.bigquery_dataset}."
        f"{settings.bigquery_table}"
    )


def create_table_if_missing(client: bigquery.Client) -> None:
    table_ref = table_id()

    schema = [
        bigquery.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("document_id", "STRING"),
        bigquery.SchemaField("project_id", "STRING"),
        bigquery.SchemaField("country", "STRING"),
        bigquery.SchemaField("year", "INTEGER"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("source_pdf_blob", "STRING"),
        bigquery.SchemaField("combined_text_blob", "STRING"),
        bigquery.SchemaField("embedding_blob", "STRING"),
        bigquery.SchemaField("page_number", "INTEGER"),
        bigquery.SchemaField("chunk_index", "INTEGER"),
        bigquery.SchemaField("chunk_order", "INTEGER"),
        bigquery.SchemaField("chunk_size", "INTEGER"),
        bigquery.SchemaField("chunk_overlap", "INTEGER"),
        bigquery.SchemaField("text", "STRING"),
        bigquery.SchemaField("text_length", "INTEGER"),
        bigquery.SchemaField("text_source", "STRING"),
        bigquery.SchemaField("embedding", "FLOAT", mode="REPEATED"),
        bigquery.SchemaField("embedding_dimension", "INTEGER"),
        bigquery.SchemaField("embedding_model", "STRING"),
        bigquery.SchemaField("embedding_status", "STRING"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("embedded_at", "TIMESTAMP"),
        bigquery.SchemaField("loaded_at", "TIMESTAMP"),
    ]

    table = bigquery.Table(table_ref, schema=schema)

    try:
        client.get_table(table_ref)
        print(f"BigQuery table already exists: {table_ref}")
    except Exception:
        client.create_table(table)
        print(f"Created BigQuery table: {table_ref}")


def clean_record(record: dict, embedding_blob: str) -> dict:
    return {
        "chunk_id": record.get("chunk_id"),
        "document_id": record.get("document_id"),
        "project_id": record.get("project_id"),
        "country": record.get("country"),
        "year": record.get("year"),
        "title": record.get("title"),
        "source_pdf_blob": record.get("source_pdf_blob"),
        "combined_text_blob": record.get("combined_text_blob"),
        "embedding_blob": embedding_blob,
        "page_number": record.get("page_number"),
        "chunk_index": record.get("chunk_index"),
        "chunk_order": record.get("chunk_order"),
        "chunk_size": record.get("chunk_size"),
        "chunk_overlap": record.get("chunk_overlap"),
        "text": record.get("text"),
        "text_length": record.get("text_length"),
        "text_source": record.get("text_source"),
        "embedding": record.get("embedding"),
        "embedding_dimension": record.get("embedding_dimension"),
        "embedding_model": record.get("embedding_model"),
        "embedding_status": record.get("embedding_status"),
        "created_at": record.get("created_at"),
        "embedded_at": record.get("embedded_at"),
        "loaded_at": utc_now(),
    }


def insert_batch(client: bigquery.Client, rows: list[dict]) -> None:
    if not rows:
        return

    errors = client.insert_rows_json(
        table_id(),
        rows,
        row_ids=[row["chunk_id"] for row in rows],
    )

    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")


def run() -> None:
    client = bigquery.Client(project=settings.project_id)
    create_table_if_missing(client)

    embedding_blobs = [
        blob
        for blob in list_blobs(settings.embeddings_prefix)
        if blob.lower().endswith(".jsonl")
    ]

    loaded_rows = 0
    failed_files = 0
    batch: list[dict] = []

    print(f"Found embedding files: {len(embedding_blobs)}")
    print(f"Loading into BigQuery table: {table_id()}")

    for embedding_blob in embedding_blobs:
        try:
            print(f"Reading embeddings: gs://{settings.bucket_name}/{embedding_blob}")

            text = download_text(embedding_blob)

            for line in text.splitlines():
                if not line.strip():
                    continue

                record = json.loads(line)

                if not record.get("chunk_id") or not record.get("embedding"):
                    continue

                batch.append(clean_record(record, embedding_blob))

                if len(batch) >= BATCH_SIZE:
                    insert_batch(client, batch)
                    loaded_rows += len(batch)
                    print(f"Loaded rows so far: {loaded_rows}")
                    batch = []

        except Exception as exc:
            failed_files += 1
            print(f"Failed to load {embedding_blob}: {exc}")

    if batch:
        insert_batch(client, batch)
        loaded_rows += len(batch)

    print()
    print("BigQuery load complete.")
    print(f"Loaded rows: {loaded_rows}")
    print(f"Failed files: {failed_files}")
    print(f"Table: {table_id()}")


if __name__ == "__main__":
    run()