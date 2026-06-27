import io
import json
from datetime import datetime, timezone

from pypdf import PdfReader

from src.common.gcs_utils import download_bytes, download_text, list_blobs, upload_text
from src.common.settings import settings


MIN_TEXT_CHARS = 500


def output_blob_name(pdf_blob: str, output_prefix: str, suffix: str = ".json") -> str:
    relative_path = pdf_blob.replace(f"{settings.raw_pdf_prefix}/", "", 1)
    return f"{output_prefix}/{relative_path}{suffix}"


def extract_text_with_pypdf(pdf_bytes: bytes) -> dict:
    reader = PdfReader(io.BytesIO(pdf_bytes))

    pages = []
    total_text = ""

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()

        pages.append(
            {
                "page_number": index,
                "text": text,
                "char_count": len(text),
            }
        )

        total_text += "\n\n" + text

    return {
        "extraction_method": "pypdf",
        "page_count": len(pages),
        "total_char_count": len(total_text.strip()),
        "pages": pages,
    }


def build_combined_text_payload(
    *,
    manifest: dict,
    extraction_result: dict,
    source: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    return {
        "document_id": manifest.get("document_id"),
        "project_id": manifest.get("project_id"),
        "country": manifest.get("country"),
        "year": manifest.get("year"),
        "title": manifest.get("title"),
        "source_pdf_blob": manifest.get("pdf_blob"),
        "text_source": source,
        "created_at": now,
        "page_count": extraction_result.get("page_count", 0),
        "total_char_count": extraction_result.get("total_char_count", 0),
        "pages": extraction_result.get("pages", []),
    }


def update_manifest(
    *,
    manifest: dict,
    manifest_blob: str,
    combined_text_blob: str,
    extraction_method: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()

    manifest["combined_text_blob"] = combined_text_blob
    manifest["text_extraction_method"] = extraction_method
    manifest["status"] = "text_extracted"
    manifest["updated_at"] = now

    upload_text(
        manifest_blob,
        json.dumps(manifest, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def run() -> None:
    manifest_blobs = [
        blob
        for blob in list_blobs(f"{settings.metadata_prefix}/manifests")
        if blob.lower().endswith(".json")
    ]

    processed_count = 0
    skipped_count = 0
    failed_count = 0
    weak_text_count = 0

    print(f"Found manifests: {len(manifest_blobs)}")

    for manifest_blob in manifest_blobs:
        try:
            manifest = json.loads(download_text(manifest_blob))
            pdf_blob = manifest.get("pdf_blob")

            if not pdf_blob:
                print(f"Skipping manifest without pdf_blob: {manifest_blob}")
                skipped_count += 1
                continue

            combined_text_blob = output_blob_name(
                pdf_blob,
                settings.combined_text_prefix,
                suffix=".json",
            )

            if manifest.get("combined_text_blob"):
                print(f"Skipped already extracted: {combined_text_blob}")
                skipped_count += 1
                continue

            print(f"Extracting text from: gs://{settings.bucket_name}/{pdf_blob}")

            pdf_bytes = download_bytes(pdf_blob)
            extraction_result = extract_text_with_pypdf(pdf_bytes)

            total_chars = extraction_result["total_char_count"]

            if total_chars < MIN_TEXT_CHARS:
                weak_text_count += 1

                # OCR fallback will be added in the next step.
                # For now, we still save the weak PyPDF result so the pipeline can continue.
                print(
                    f"Weak PyPDF text detected "
                    f"({total_chars} chars). OCR fallback will be added next."
                )

            payload = build_combined_text_payload(
                manifest=manifest,
                extraction_result=extraction_result,
                source="pypdf",
            )

            upload_text(
                combined_text_blob,
                json.dumps(payload, ensure_ascii=False, indent=2),
                content_type="application/json",
            )

            update_manifest(
                manifest=manifest,
                manifest_blob=manifest_blob,
                combined_text_blob=combined_text_blob,
                extraction_method="pypdf",
            )

            processed_count += 1

            print(f"Saved text: gs://{settings.bucket_name}/{combined_text_blob}")

        except Exception as exc:
            failed_count += 1
            print(f"Failed to extract text for {manifest_blob}: {exc}")

    print()
    print("Text extraction complete.")
    print(f"Processed documents: {processed_count}")
    print(f"Skipped documents: {skipped_count}")
    print(f"Weak text documents: {weak_text_count}")
    print(f"Failed documents: {failed_count}")


if __name__ == "__main__":
    run()