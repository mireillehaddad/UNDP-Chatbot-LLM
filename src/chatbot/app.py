import streamlit as st

from src.chatbot.qa import ask
from src.common.settings import settings


st.set_page_config(
    page_title="UNDP Project Document Chatbot",
    layout="wide",
)

st.title("UNDP Project Document Chatbot")
st.write(
    "Ask questions about UNDP project documents. "
    "The chatbot retrieves relevant document sections from BigQuery "
    "and uses Gemini to generate grounded answers."
)


st.markdown("---")

question = st.text_area(
    "Question",
    placeholder="Example: What projects are currently active in Lebanon?",
    height=120,
)

if st.button("Ask"):
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Searching documents and generating answer..."):
            answer, sources = ask(question.strip())

        st.subheader("Answer")
        st.write(answer)

        st.subheader("Sources")

        for i, source in enumerate(sources, start=1):
            title = source.get("title", "Untitled document")
            country = source.get("country", "Unknown")
            year = source.get("year", "Unknown")
            page = source.get("page_number", "Unknown")
            score = source.get("score", 0)

            with st.expander(
                f"Source {i} | {title} | {country} | {year} | Page {page} | Score {score:.3f}"
            ):
                st.markdown(
                    f"""
                    **Country:** {country}  
                    **Year:** {year}  
                    **Project ID:** {source.get("project_id")}  
                    **Document ID:** {source.get("document_id")}  
                    **Page:** {page}  
                    **Score:** {score:.3f}
                    """
                )

                st.markdown("**Relevant excerpt**")
                st.write(source.get("text", ""))

                st.markdown("**Source PDF**")
                st.code(source.get("source_pdf_blob", ""))

st.markdown("---")

with st.expander("Example Questions"):
    st.markdown(
        """
        - What projects are currently active in Lebanon?
        - Which UNDP projects focus on climate change?
        - What projects improve access to clean drinking water?
        - What is the budget of a specific project?
        - What outcomes are expected from a project?
        - Which stakeholders are involved in a project?
        """
    )

with st.expander("About This Project"):
    st.markdown(
        """
        ### Problem

        UNDP publishes project documents in PDF format through the **Open UNDP** platform **Open UNDP:** https://open.undp.org/

        Finding specific information across hundreds of pages of project documents is difficult and time-consuming.

        ### Solution

        This project implements a fully automated **Retrieval-Augmented Generation (RAG)** pipeline on Google Cloud Platform for querying UNDP project documents.

        **Data Ingestion:** Python ingestion scripts connect to the Open UNDP API to retrieve project metadata and download PDF documents, which are stored in Google Cloud Storage.

        **Document Processing:** PDF documents are processed using custom Python pipelines that extract text using PyPDF with Document AI OCR fallback and split documents into overlapping chunks to preserve context and improve retrieval quality.

        **Embedding Generation:** Vector embeddings are generated for each document chunk using Vertex AI Gemini Embeddings and stored in Google Cloud Storage.

        **BigQuery Vector Search:** Generated embeddings are loaded into BigQuery, where semantic similarity search retrieves the most relevant document chunks.

        **Retrieval-Augmented Generation (RAG):** When a user submits a question, the application generates an embedding for the query, retrieves the most relevant document chunks using BigQuery, and provides the retrieved context to Gemini to generate grounded answers based only on the UNDP project documents.

        **Application Layer:** A Streamlit chatbot provides an interactive interface and is deployed as a serverless application on Cloud Run.

        **Pipeline Orchestration:** The data pipeline is automated using Cloud Run Jobs for ingestion, document processing, embedding generation, and loading embeddings into BigQuery. The jobs are orchestrated using Cloud Workflows and executed on a schedule by Cloud Scheduler.

        **CI/CD:** GitHub, Cloud Build, Docker, and Artifact Registry automate container image builds, deployments, and application updates.
        """
    )

with st.expander("Architecture"):
    st.code(
        """
Open UNDP API
        ↓
Google Cloud Storage
        ↓
PyPDF extraction + Document AI OCR fallback
        ↓
Chunking
        ↓
Gemini embeddings
        ↓
BigQuery semantic retrieval
        ↓
Gemini answer generation
        ↓
Streamlit chatbot
        """
    )

with st.expander("Data Source"):
    st.markdown(
        """
**Open UNDP Website**

https://open.undp.org/

**Open UNDP API Documentation**

https://api.open.undp.org/api_documentation/api#!/default/individual_project_data
"""
    )