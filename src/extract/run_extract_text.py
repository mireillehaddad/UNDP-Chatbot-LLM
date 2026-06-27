import io
import json
from datetime import datetime, timezone

from google.cloud import documentai
from google.protobuf.json_format import MessageToDict
from pypdf import PdfReader

from src.common.gcs_utils import download_bytes, download_text, list_blobs, upload_text
from src.common.settings import settings


MIN_TEXT_CHARS = 500
MAX_OCR_PAGES_SYNC = 15


def output_blob_name(pdf_blob: str, output_prefix: str, suffix: str = ".json") -> str:
    relative_path = pdf_blob.replace(f"{settings.raw_pdf_prefix}/", "", 1)
    return f"{output_prefix}/{relative_path}{suffix}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_text_with_pypdf(pdf_bytes: bytes) -> dict:
    reader = PdfReader(io.BytesIO(pdf_bytes))

    pages = []
    total_text = ""

    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()

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


def extract_text_with_document_ai(pdf_bytes: bytes) -> tuple[dict, dict]:
    client = documentai.DocumentProcessorServiceClient(
        client_options={
            "api_endpoint": f"{settings.document_ai_location}-documentai.googleapis.com"
        }
    )

    processor_name = client.processor_path(
        settings.project_id,
        settings.document_ai_location,
        settings.document_ai_processor_id,
    )

    raw_document = documentai.RawDocument(
        content=pdf_bytes,
        mime_type="application/pdf",
    )

    process_options = documentai.ProcessOptions(
        individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(
            pages=list(range(1, MAX_OCR_PAGES_SYNC + 1))
        )
    )

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=raw_document,
        process_options=process_options,
    )

    result = client.process_document(request=request)
    document = result.document

    document_dict = MessageToDict(
        document._pb,
        preserving_proto_field_name=True,
    )

    pages = []

    for page_index, page in enumerate(document.pages, start=1):
        text_segments = []

        for segment in page.layout.text_anchor.text_segments:
            start_index = int(segment.start_index or 0)
            end_index = int(segment.end_index or 0)
            text_segments.append(document.text[start_index:end_index])

        page_text = "".join(text_segments).strip()

        pages.append(
            {
                "page_number": page_index,
                "text": page_text,
                "char_count": len(page_text),
            }
        )

    total_text = "\n\n".join(page["text"] for page in pages).strip()

    extraction_result = {
        "extraction_method": "document_ai_ocr",
        "page_count": len(pages),
        "total_char_count": len(total_text),
        "pages": pages,
    }

    return extraction_result, document_dict


def build_combined_text_payload(
    *,
    manifest: dict,
    extraction_result: dict,
    source: str,
) -> dict:
    return {
        "document_id": manifest.get("document_id"),
        "project_id": manifest.get("project_id"),
        "country": manifest.get("country"),
        "year": manifest.get("year"),
        "title": manifest.get("title"),
        "source_pdf_blob": manifest.get("pdf_blob"),
        "text_source": source,
        "created_at": utc_now(),
        "page_count": extraction_result.get("page_count", 0),
        "total_char_count": extraction_result.get("total_char_count", 0),
        "pages": extraction_result.get("pages", []),
    }


def save_manifest(manifest: dict, manifest_blob: str) -> None:
    manifest["updated_at"] = utc_now()

    upload_text(
        manifest_blob,
        json.dumps(manifest, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def update_manifest_success(
    *,
    manifest: dict,
    manifest_blob: str,
    combined_text_blob: str,
    extraction_method: str,
    ocr_json_blob: str | None = None,
    ocr_text_blob: str | None = None,
) -> None:
    manifest["combined_text_blob"] = combined_text_blob
    manifest["text_extraction_method"] = extraction_method
    manifest["status"] = "text_extracted"

    if ocr_json_blob:
        manifest["ocr_json_blob"] = ocr_json_blob

    if ocr_text_blob:
        manifest["ocr_text_blob"] = ocr_text_blob

    save_manifest(manifest, manifest_blob)


def update_manifest_ocr_failed(
    *,
    manifest: dict,
    manifest_blob: str,
    error: Exception,
) -> None:
    manifest["status"] = "ocr_failed"
    manifest["ocr_error"] = str(error)
    manifest["text_extraction_method"] = "document_ai_ocr_failed"

    save_manifest(manifest, manifest_blob)


def run() -> None:
    manifest_blobs = [
        blob
        for blob in list_blobs(f"{settings.metadata_prefix}/manifests")
        if blob.lower().endswith(".json")
    ]

    processed_count = 0
    skipped_count = 0
    failed_count = 0
    ocr_count = 0
    pypdf_count = 0

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
                existing_payload = json.loads(download_text(manifest["combined_text_blob"]))
                existing_chars = existing_payload.get("total_char_count", 0)
                existing_source = existing_payload.get("text_source", "")

                if existing_chars >= MIN_TEXT_CHARS:
                    print(f"Skipped already extracted: {combined_text_blob}")
                    skipped_count += 1
                    continue

                if existing_source == "document_ai_ocr":
                    print(f"Skipped already OCR extracted: {combined_text_blob}")
                    skipped_count += 1
                    continue

                print(
                    f"Reprocessing weak extraction with OCR: "
                    f"{combined_text_blob} ({existing_chars} chars)"
                )

            print(f"Extracting text from: gs://{settings.bucket_name}/{pdf_blob}")

            pdf_bytes = download_bytes(pdf_blob)

            extraction_result = extract_text_with_pypdf(pdf_bytes)
            extraction_method = "pypdf"
            ocr_json_blob = None
            ocr_text_blob = None

            if extraction_result["total_char_count"] < MIN_TEXT_CHARS:
                print(
                    f"Weak PyPDF text detected "
                    f"({extraction_result['total_char_count']} chars). Running OCR..."
                )

                try:
                    extraction_result, ocr_json = extract_text_with_document_ai(pdf_bytes)
                except Exception as exc:
                    update_manifest_ocr_failed(
                        manifest=manifest,
                        manifest_blob=manifest_blob,
                        error=exc,
                    )
                    failed_count += 1
                    print(f"OCR failed for {pdf_blob}: {exc}")
                    continue

                extraction_method = "document_ai_ocr"
                ocr_count += 1

                ocr_json_blob = output_blob_name(
                    pdf_blob,
                    settings.ocr_json_prefix,
                    suffix=".json",
                )

                ocr_text_blob = output_blob_name(
                    pdf_blob,
                    settings.ocr_text_prefix,
                    suffix=".json",
                )

                upload_text(
                    ocr_json_blob,
                    json.dumps(ocr_json, ensure_ascii=False, indent=2),
                    content_type="application/json",
                )

                upload_text(
                    ocr_text_blob,
                    json.dumps(extraction_result, ensure_ascii=False, indent=2),
                    content_type="application/json",
                )

                print(f"Saved OCR JSON: gs://{settings.bucket_name}/{ocr_json_blob}")
                print(f"Saved OCR text: gs://{settings.bucket_name}/{ocr_text_blob}")

            else:
                pypdf_count += 1

            payload = build_combined_text_payload(
                manifest=manifest,
                extraction_result=extraction_result,
                source=extraction_method,
            )

            upload_text(
                combined_text_blob,
                json.dumps(payload, ensure_ascii=False, indent=2),
                content_type="application/json",
            )

            update_manifest_success(
                manifest=manifest,
                manifest_blob=manifest_blob,
                combined_text_blob=combined_text_blob,
                extraction_method=extraction_method,
                ocr_json_blob=ocr_json_blob,
                ocr_text_blob=ocr_text_blob,
            )

            processed_count += 1
            print(f"Saved final text: gs://{settings.bucket_name}/{combined_text_blob}")

        except Exception as exc:
            failed_count += 1
            print(f"Failed to extract text for {manifest_blob}: {exc}")

    print()
    print("Text extraction complete.")
    print(f"Processed documents: {processed_count}")
    print(f"Skipped documents: {skipped_count}")
    print(f"Used PyPDF: {pypdf_count}")
    print(f"Used OCR fallback: {ocr_count}")
    print(f"Failed documents: {failed_count}")


if __name__ == "__main__":
    run()