from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vector_store = FAISS.load_local(
    "faiss_index",
    embedding,
    allow_dangerous_deserialization=True
)

retriever = vector_store.as_retriever(search_kwargs={"k": 3})


def get_rag_context(query: str) -> str:
    docs = retriever.invoke(query)

    if not docs:
        return ""

    return "\n".join(
        f"""
REFERENCE MATERIAL (DO NOT USE AS DATA):
{d.page_content}
"""
        for d in docs
    )

