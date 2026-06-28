from google import genai

from src.common.settings import settings
from src.retrieval.retriever import retrieve


SYSTEM_PROMPT = """
You are a UNDP project assistant.

Answer only using the retrieved document context.
If the answer is not in the context, say:
'I could not find this information in the available UNDP project documents.'

Always cite sources using [Source 1], [Source 2], etc.
Do not make up facts.
"""


def build_context(records: list[dict]) -> str:
    sections = []

    for i, record in enumerate(records, start=1):
        score = record.get("score", 0.0)

        sections.append(
            f"""
==================================================
Source {i}

Country          : {record["country"]}
Year             : {record["year"]}
Project ID       : {record["project_id"]}
Document ID      : {record["document_id"]}
Title            : {record["title"]}
Page             : {record["page_number"]}
Chunk            : {record["chunk_index"]}
Chunk Order      : {record["chunk_order"]}
Similarity Score : {score:.4f}

--------------------------------------------------
Document Text
--------------------------------------------------

{record["text"]}

==================================================
"""
        )

    return "\n".join(sections)


def ask(question: str, top_k: int = 5) -> tuple[str, list[dict]]:
    sources = retrieve(question, top_k=top_k)
    context = build_context(sources)

    prompt = f"""
Context:
{context}

Question:
{question}
"""

    client = genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.region,
    )

    response = client.models.generate_content(
        model=settings.generation_model,
        contents=[SYSTEM_PROMPT, prompt],
    )

    return response.text, sources


if __name__ == "__main__":
    answer, sources = ask("What projects improve access to clean drinking water?")

    print("ANSWER")
    print(answer)

    print("\nSOURCES")
    for i, source in enumerate(sources, start=1):
        print(
            f"[Source {i}] {source['country']} | "
            f"{source['year']} | "
            f"{source['title']} | "
            f"Page {source['page_number']} | "
            f"Score {source['score']:.3f}"
        )