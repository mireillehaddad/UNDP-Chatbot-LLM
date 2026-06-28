import streamlit as st

from src.chatbot.qa import ask


st.set_page_config(
    page_title="UNDP Project Document Chatbot",
    page_icon="🌍",
    layout="wide",
)


st.title("🌍 UNDP Project Document Chatbot")
st.caption("Ask questions about UNDP project documents using BigQuery vector search and Gemini.")


with st.sidebar:
    st.header("About")
    st.write(
        """
        This chatbot retrieves relevant UNDP project document chunks from BigQuery
        and uses Gemini to generate grounded answers.
        """
    )

    top_k = st.slider(
        "Number of sources",
        min_value=3,
        max_value=10,
        value=5,
        step=1,
    )


question = st.text_area(
    "Ask a question",
    placeholder="Example: What projects are currently active in Lebanon?",
    height=120,
)

ask_button = st.button("Ask", type="primary")


if ask_button:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Retrieving sources and generating answer..."):
            answer, sources = ask(question.strip(), top_k=top_k)

        st.subheader("Answer")
        st.write(answer)

        st.subheader("Sources")

        for i, source in enumerate(sources, start=1):
            title = source.get("title", "Untitled document")
            country = source.get("country", "Unknown")
            year = source.get("year", "Unknown")
            page = source.get("page_number", "Unknown")
            score = source.get("score", 0.0)

            with st.expander(
                f"Source {i} · {title} · {country} · {year} · Page {page} · Score {score:.3f}"
            ):
                st.markdown(
                    f"""
                    **Country:** {country}  
                    **Year:** {year}  
                    **Project ID:** {source.get("project_id")}  
                    **Document ID:** {source.get("document_id")}  
                    **Page:** {page}  
                    **Score:** {score:.3f}  
                    **Text source:** {source.get("text_source")}  
                    """
                )

                st.markdown("**Relevant excerpt:**")
                st.write(source.get("text", ""))

                st.markdown("**GCS source PDF:**")
                st.code(source.get("source_pdf_blob", ""))