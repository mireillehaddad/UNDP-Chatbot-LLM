import hashlib
import json
from datetime import datetime, timezone

from src.common.gcs_utils import download_text, list_blobs, upload_text
from src.common.settings import settings


CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
MIN_TEXT_CHARS = 500


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def output_blob_name(input_blob: str) -> str:
    relative_path = input_blob.replace(f"{settings.combined_text_prefix}/", "", 1)
    return f"{settings.chunks_prefix}/{relative_path}.jsonl"


def chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def make_chunk_id(
    *,
    document_id: str,
    project_id: str,
    page_number: int,
    chunk_index: int,
    text: str,
) -> str:
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{project_id}_{document_id}_p{page_number}_c{chunk_index}_{text_hash}"


def run() -> None:
    combined_blobs = [
        blob
        for blob in list_blobs(settings.combined_text_prefix)
        if blob.lower().endswith(".json")
    ]

    processed_count = 0
    skipped_count = 0
    chunk_count = 0
    failed_count = 0

    print(f"Found combined text files: {len(combined_blobs)}")

    for combined_blob in combined_blobs:
        try:
            output_blob = output_blob_name(combined_blob)

            payload = json.loads(download_text(combined_blob))
            total_chars = payload.get("total_char_count", 0)

            if total_chars < MIN_TEXT_CHARS:
                print(f"Skipping weak text: {combined_blob} ({total_chars} chars)")
                skipped_count += 1
                continue

            document_id = str(payload.get("document_id", "unknown"))
            project_id = str(payload.get("project_id", "unknown"))

            pages = payload.get("pages", [])
            records = []
            chunk_order = 0

            for page in pages:
                page_number = int(page.get("page_number") or 0)
                page_text = page.get("text", "") or ""

                page_chunks = chunk_text(page_text)

                for index, chunk in enumerate(page_chunks, start=1):
                    chunk_order += 1

                    chunk_id = make_chunk_id(
                        document_id=document_id,
                        project_id=project_id,
                        page_number=page_number,
                        chunk_index=index,
                        text=chunk,
                    )

                    records.append(
                        {
                            "chunk_id": chunk_id,
                            "document_id": document_id,
                            "project_id": project_id,
                            "country": payload.get("country"),
                            "year": payload.get("year"),
                            "title": payload.get("title"),
                            "source_pdf_blob": payload.get("source_pdf_blob"),
                            "combined_text_blob": combined_blob,
                            "page_number": page_number,
                            "chunk_index": index,
                            "chunk_order": chunk_order,
                            "chunk_size": CHUNK_SIZE,
                            "chunk_overlap": CHUNK_OVERLAP,
                            "text": chunk,
                            "text_length": len(chunk),
                            "text_source": payload.get("text_source"),
                            "embedding_status": "pending",
                            "created_at": utc_now(),
                        }
                    )

            if not records:
                print(f"No chunks created: {combined_blob}")
                skipped_count += 1
                continue

            jsonl_text = "\n".join(
                json.dumps(record, ensure_ascii=False)
                for record in records
            )

            upload_text(
                output_blob,
                jsonl_text,
                content_type="application/jsonl",
            )

            processed_count += 1
            chunk_count += len(records)

            print(f"Chunked: {combined_blob}")
            print(f"Saved chunks: gs://{settings.bucket_name}/{output_blob}")
            print(f"Chunks created: {len(records)}")

        except Exception as exc:
            failed_count += 1
            print(f"Failed to chunk {combined_blob}: {exc}")

    print()
    print("Chunking complete.")
    print(f"Processed files: {processed_count}")
    print(f"Skipped files: {skipped_count}")
    print(f"Total chunks created: {chunk_count}")
    print(f"Failed files: {failed_count}")


if __name__ == "__main__":
    run()