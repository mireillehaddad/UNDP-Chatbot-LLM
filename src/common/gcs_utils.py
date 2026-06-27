from google.cloud import storage

from src.common.settings import settings


def get_bucket():
    client = storage.Client(project=settings.project_id)
    return client.bucket(settings.bucket_name)


def blob_exists(blob_name: str) -> bool:
    bucket = get_bucket()
    return bucket.blob(blob_name).exists()


def upload_bytes(blob_name: str, data: bytes, content_type: str | None = None) -> None:
    bucket = get_bucket()
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)


def upload_text(blob_name: str, text: str, content_type: str = "text/plain") -> None:
    upload_bytes(blob_name, text.encode("utf-8"), content_type=content_type)


def download_bytes(blob_name: str) -> bytes:
    bucket = get_bucket()
    return bucket.blob(blob_name).download_as_bytes()


def download_text(blob_name: str) -> str:
    return download_bytes(blob_name).decode("utf-8")


def list_blobs(prefix: str) -> list[str]:
    bucket = get_bucket()
    return [blob.name for blob in bucket.list_blobs(prefix=prefix)]


def output_blob_name(
    input_blob_name: str,
    input_prefix: str,
    output_prefix: str,
    suffix: str,
) -> str:
    relative_path = input_blob_name.replace(f"{input_prefix}/", "", 1)
    return f"{output_prefix}/{relative_path}{suffix}"