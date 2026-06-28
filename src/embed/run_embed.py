import json
import time
from datetime import datetime, timezone

from google import genai
from google.genai.types import EmbedContentConfig

from src.common.gcs_utils import download_text, list_blobs, upload_text
from src.common.settings import settings


SLEEP_SECONDS = 0.1
EMBEDDING_DIMENSION = 768


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def output_blob_name(chunk_blob: str) -> str:
    relative_path = chunk_blob.replace(f"{settings.chunks_prefix}/", "", 1)
    return f"{settings.embeddings_prefix}/{relative_path}"


def embed_text(client: genai.Client, text: str) -> list[float]:
    response = client.models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config=EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIMENSION,
        ),
    )

    return response.embeddings[0].values


def run() -> None:
    client = genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.region,
    )

    chunk_blobs = [
        blob
        for blob in list_blobs(settings.chunks_prefix)
        if blob.lower().endswith(".jsonl")
    ]

    processed_files = 0
    embedded_chunks = 0
    failed_files = 0

    print(f"Found chunk files: {len(chunk_blobs)}")

    for chunk_blob in chunk_blobs:
        try:
            output_blob = output_blob_name(chunk_blob)

            print(f"Embedding chunks from: gs://{settings.bucket_name}/{chunk_blob}")

            lines = download_text(chunk_blob).splitlines()
            output_records = []

            for line in lines:
                if not line.strip():
                    continue

                record = json.loads(line)
                text = record.get("text", "")

                if not text:
                    continue

                embedding = embed_text(client, text)

                output_records.append(
                    {
                        **record,
                        "embedding": embedding,
                        "embedding_dimension": EMBEDDING_DIMENSION,
                        "embedding_model": settings.embedding_model,
                        "embedding_status": "embedded",
                        "embedded_at": utc_now(),
                    }
                )

                embedded_chunks += 1
                time.sleep(SLEEP_SECONDS)

            if not output_records:
                print(f"No embeddings created for: {chunk_blob}")
                continue

            jsonl_text = "\n".join(
                json.dumps(record, ensure_ascii=False)
                for record in output_records
            )

            upload_text(
                output_blob,
                jsonl_text,
                content_type="application/jsonl",
            )

            processed_files += 1

            print(f"Saved embeddings: gs://{settings.bucket_name}/{output_blob}")
            print(f"Embedded chunks: {len(output_records)}")

        except Exception as exc:
            failed_files += 1
            print(f"Failed to embed {chunk_blob}: {exc}")

    print()
    print("Embedding complete.")
    print(f"Processed chunk files: {processed_files}")
    print(f"Embedded chunks: {embedded_chunks}")
    print(f"Failed files: {failed_files}")


if __name__ == "__main__":
    run()