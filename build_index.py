from pathlib import Path
from langchain_community.document_loaders import CSVLoader, PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

DOCS_DIR = Path("Account_docs")
INDEX_DIR = "faiss_index"

def load_documents():
    documents = []

    # Load CSV
    for csv_file in DOCS_DIR.glob("*.csv"):
        loader = CSVLoader(str(csv_file), encoding="utf-8")
        docs = loader.load()
        for d in docs:
            d.metadata["source"] = csv_file.name
        documents.extend(docs)

    # Load PDFs
    for pdf_file in DOCS_DIR.glob("*.pdf"):
        loader = PyPDFLoader(str(pdf_file))
        docs = loader.load()

        splitter = CharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        split_docs = splitter.split_documents(docs)

        for d in split_docs:
            d.metadata["source"] = pdf_file.name

        documents.extend(split_docs)

    return documents


def main():
    docs = load_documents()
    print(f"Loaded {len(docs)} documents")

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(INDEX_DIR)

    print("FAISS index created successfully")


if __name__ == "__main__":
    main()
