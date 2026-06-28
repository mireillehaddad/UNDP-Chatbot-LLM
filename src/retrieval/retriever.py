from google import genai
from google.cloud import bigquery
from google.genai.types import EmbedContentConfig

from src.common.settings import settings


TOP_K = 5
EMBEDDING_DIMENSION = 768


def table_id() -> str:
    return (
        f"{settings.project_id}."
        f"{settings.bigquery_dataset}."
        f"{settings.bigquery_table}"
    )


def embed_query(client: genai.Client, query: str) -> list[float]:
    response = client.models.embed_content(
        model=settings.embedding_model,
        contents=query,
        config=EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIMENSION,
        ),
    )

    return response.embeddings[0].values


def retrieve(question: str, top_k: int = TOP_K) -> list[dict]:
    genai_client = genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.region,
    )

    bq_client = bigquery.Client(project=settings.project_id)

    query_embedding = embed_query(genai_client, question)

    sql = f"""
    SELECT
        chunk_id,
        document_id,
        project_id,
        country,
        year,
        title,
        page_number,
        chunk_index,
        chunk_order,
        text,
        text_length,
        text_source,
        source_pdf_blob,
        embedding_blob,
        ML.DISTANCE(
            embedding,
            @query_embedding,
            'COSINE'
        ) AS distance
    FROM `{table_id()}`
    WHERE embedding IS NOT NULL
    ORDER BY distance ASC
    LIMIT @candidate_k
    """

    candidate_k = top_k * 5

    job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ArrayQueryParameter(
            "query_embedding",
            "FLOAT64",
            query_embedding,
        ),
        bigquery.ScalarQueryParameter(
            "candidate_k",
            "INT64",
            candidate_k,
        ),
     ]
   )

    rows = bq_client.query(sql, job_config=job_config).result()

    seen = set()
    results = []

    for row in rows:
        text_key = row["text"][:300].strip().lower()

        key = (
        row["document_id"],
        row["page_number"],
         )

        if key in seen:
            continue

        seen.add(key)

        distance = float(row["distance"])
        score = 1.0 - distance

        results.append(
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "project_id": row["project_id"],
                "country": row["country"],
                "year": row["year"],
                "title": row["title"],
                "page_number": row["page_number"],
                "chunk_index": row["chunk_index"],
                "chunk_order": row["chunk_order"],
                "text": row["text"],
                "text_length": row["text_length"],
                "text_source": row["text_source"],
                "source_pdf_blob": row["source_pdf_blob"],
                "embedding_blob": row["embedding_blob"],
                "distance": distance,
                "score": score,
            }
        )

        if len(results) >= top_k:
            break

    return results


if __name__ == "__main__":
    test_question = "What projects improve access to clean water?"

    results = retrieve(test_question, top_k=5)

    for index, result in enumerate(results, start=1):
        print()
        print(f"Result {index}")
        print(f"Score: {result['score']:.4f}")
        print(f"Country: {result['country']}")
        print(f"Year: {result['year']}")
        print(f"Project ID: {result['project_id']}")
        print(f"Title: {result['title']}")
        print(f"Page: {result['page_number']}")
        print(result["text"][:500])