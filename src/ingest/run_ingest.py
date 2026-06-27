import csv
import io
import json
import re
from datetime import datetime, timezone


import requests

from src.common.gcs_utils import blob_exists, list_blobs, upload_bytes, upload_text
from src.common.settings import settings


UNDP_PROJECT_LIST_URL = "https://api.open.undp.org/api/project_list/?year={year}"
UNDP_PROJECT_DETAILS_URL = "https://api.open.undp.org/api/projects/{project_id}.json"


def safe_filename(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[^\w\-.]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text[:180]


def get_project_list(year: int) -> list[dict]:
    url = UNDP_PROJECT_LIST_URL.format(year=year)
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    data = response.json()
    projects_data = data.get("data", {})

    if isinstance(projects_data, dict):
        projects = projects_data.get("data", [])
    else:
        projects = projects_data

    return projects if isinstance(projects, list) else []


def get_project_details(project_id: str) -> dict:
    url = UNDP_PROJECT_DETAILS_URL.format(project_id=project_id)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def extract_documents(project_details: dict) -> list[dict]:
    documents = project_details.get("documents", [])

    if isinstance(documents, dict):
        documents = documents.get("data", [])

    return documents if isinstance(documents, list) else []


def get_pdf_url(document: dict) -> str | None:
    for key in ["url", "download_url", "document_url", "file_url"]:
        value = document.get(key)
        if value and ".pdf" in str(value).lower():
            return str(value)

    return None


def download_pdf(url: str) -> bytes:
    response = requests.get(
        url,
        timeout=(15, 60),
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if "pdf" not in content_type and not url.lower().endswith(".pdf"):
        raise ValueError(f"URL does not appear to be a PDF. Content-Type={content_type}")

    return response.content


def country_matches(project: dict) -> bool:
    country = str(
        project.get("country")
        or project.get("country_name")
        or project.get("countryname")
        or ""
    ).strip()

    return country in settings.countries


def build_manifest(
    *,
    year: int,
    country: str,
    project_id: str,
    document_id: str,
    title: str,
    pdf_url: str,
    pdf_blob: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    return {
        "year": year,
        "country": country,
        "project_id": project_id,
        "document_id": document_id,
        "title": title,
        "pdf_url": pdf_url,
        "pdf_blob": pdf_blob,
        "pdf_text_blob": None,
        "ocr_json_blob": None,
        "ocr_text_blob": None,
        "combined_text_blob": None,
        "chunks_blob": None,
        "embeddings_blob": None,
        "status": "downloaded",
        "created_at": now,
        "updated_at": now,
    }

def print_pdf_counts() -> None:
    pdf_blobs = [
        blob
        for blob in list_blobs(settings.raw_pdf_prefix)
        if blob.lower().endswith(".pdf")
    ]

    unique_document_ids = {
        blob.split("/")[-1].split("_")[0]
        for blob in pdf_blobs
    }

    unique_project_ids = {
        part.replace("project_id=", "")
        for blob in pdf_blobs
        for part in blob.split("/")
        if part.startswith("project_id=")
    }

    print()
    print("PDF inventory.")
    print(f"Total PDF files in bucket: {len(pdf_blobs)}")
    print(f"Unique document IDs: {len(unique_document_ids)}")
    print(f"Unique project IDs: {len(unique_project_ids)}")

def run() -> None:
    uploaded_count = 0
    skipped_count = 0
    metadata_rows: list[dict] = []

    for year in settings.years:
        print(f"Fetching UNDP projects for year={year}")

        projects = get_project_list(year)

        for project in projects:
            if uploaded_count >= settings.max_new_pdfs:
                break

            if not country_matches(project):
                continue

            project_id = str(
                project.get("project_id")
                or project.get("id")
                or project.get("projectid")
                or ""
            ).strip()

            if not project_id:
                continue

            country = str(
                project.get("country")
                or project.get("country_name")
                or project.get("countryname")
                or "unknown"
            ).strip()

            try:
                details = get_project_details(project_id)
            except Exception as exc:
                print(f"Skipping project {project_id}: could not fetch details: {exc}")
                continue

            documents = extract_documents(details)

            for document in documents:
                if uploaded_count >= settings.max_new_pdfs:
                    break

                title = str(
                    document.get("title")
                    or document.get("name")
                    or document.get("document_name")
                    or "document"
                ).strip()

                title_lower = title.lower()

                if not any(
                    keyword.lower() in title_lower
                    for keyword in settings.document_keywords
                ):
                    continue

                pdf_url = get_pdf_url(document)

                if not pdf_url:
                    continue

                document_id = str(
                    document.get("id")
                    or document.get("document_id")
                    or safe_filename(title)
                ).strip()

                file_name = f"{document_id}_{safe_filename(title)}.pdf"

                base_path = (
                    f"year={year}/"
                    f"country={safe_filename(country)}/"
                    f"project_id={project_id}/"
                    f"{file_name}"
                )

                pdf_blob = f"{settings.raw_pdf_prefix}/{base_path}"
                manifest_blob = f"{settings.metadata_prefix}/manifests/{base_path}.json"

                if blob_exists(pdf_blob):
                    skipped_count += 1
                    print(f"Skipped existing PDF: gs://{settings.bucket_name}/{pdf_blob}")
                    continue

                try:
                    print(f"Downloading PDF: {title}")
                    pdf_bytes = download_pdf(pdf_url)

                    upload_bytes(
                        pdf_blob,
                        pdf_bytes,
                        content_type="application/pdf",
                    )

                    manifest = build_manifest(
                        year=year,
                        country=country,
                        project_id=project_id,
                        document_id=document_id,
                        title=title,
                        pdf_url=pdf_url,
                        pdf_blob=pdf_blob,
                    )

                    upload_text(
                        manifest_blob,
                        json.dumps(manifest, ensure_ascii=False, indent=2),
                        content_type="application/json",
                    )

                    metadata_rows.append(
                        {
                            "year": year,
                            "country": country,
                            "project_id": project_id,
                            "document_id": document_id,
                            "title": title,
                            "pdf_url": pdf_url,
                            "pdf_blob": pdf_blob,
                            "manifest_blob": manifest_blob,
                            "uploaded_at": manifest["created_at"],
                        }
                    )

                    uploaded_count += 1

                    print(f"Uploaded PDF: gs://{settings.bucket_name}/{pdf_blob}")
                    print(f"Uploaded manifest: gs://{settings.bucket_name}/{manifest_blob}")

                except Exception as exc:
                    print(f"Failed to process document {title}: {exc}")

    if metadata_rows:
        output = io.StringIO()

        writer = csv.DictWriter(
            output,
            fieldnames=metadata_rows[0].keys(),
        )

        writer.writeheader()
        writer.writerows(metadata_rows)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        metadata_blob = f"{settings.metadata_prefix}/ingest_metadata_{timestamp}.csv"

        upload_text(metadata_blob, output.getvalue())

        print(f"Uploaded metadata CSV: gs://{settings.bucket_name}/{metadata_blob}")

    print()
    print("Ingestion complete.")
    print(f"Uploaded new PDFs: {uploaded_count}")
    print(f"Skipped existing PDFs: {skipped_count}")
    print_pdf_counts()


if __name__ == "__main__":
    run()