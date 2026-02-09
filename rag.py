import os
from dotenv import load_dotenv
from langchain_community.document_loaders import CSVLoader, PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
from langchain_ollama import OllamaLLM
from pathlib import Path

# 🔐 Load environment variables
load_dotenv()

# 📁 Define the folder path containing CSV and PDF files
documents_folder_path = "C:/Users/Shilpa/Desktop/Gurukul/Account_docs"

# 📄 Load all CSV and PDF files from the folder
def load_documents_from_folder(folder_path):
    """
    Load all CSV and PDF files from a specified folder.
    
    Args:
        folder_path (str): Path to the folder containing CSV and PDF files
        
    Returns:
        list: Combined list of documents from all files
    """
    all_documents = []
    folder = Path(folder_path)
    
    # Find all CSV and PDF files
    csv_files = list(folder.glob("*.csv"))
    pdf_files = list(folder.glob("*.pdf"))
    
    if not csv_files and not pdf_files:
        print(f"⚠️ No CSV or PDF files found in {folder_path}")
        return all_documents
    
    print(f"📂 Found {len(csv_files)} CSV file(s) and {len(pdf_files)} PDF file(s):")
    
    # Load CSV files
    for csv_file in csv_files:
        try:
            print(f"   📄 Loading CSV: {csv_file.name}")
            loader = CSVLoader(file_path=str(csv_file), encoding="utf-8")
            documents = loader.load()
            
            # Add source metadata
            for doc in documents:
                doc.metadata['source_file'] = csv_file.name
                doc.metadata['file_type'] = 'CSV'
            
            all_documents.extend(documents)
            print(f"   ✅ Loaded {len(documents)} records from {csv_file.name}")
            
        except Exception as e:
            print(f"   ❌ Error loading {csv_file.name}: {str(e)}")
            continue
    
    # Load PDF files
    for pdf_file in pdf_files:
        try:
            print(f"   📕 Loading PDF: {pdf_file.name}")
            loader = PyPDFLoader(str(pdf_file))
            documents = loader.load()
            
            # Add source metadata
            for doc in documents:
                doc.metadata['source_file'] = pdf_file.name
                doc.metadata['file_type'] = 'PDF'
            
            # Optional: Split PDF documents into smaller chunks for better retrieval
            text_splitter = CharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separator="\n"
            )
            split_documents = text_splitter.split_documents(documents)
            
            all_documents.extend(split_documents)
            print(f"   ✅ Loaded {len(documents)} pages from {pdf_file.name} (split into {len(split_documents)} chunks)")
            
        except Exception as e:
            print(f"   ❌ Error loading {pdf_file.name}: {str(e)}")
            continue
    
    print(f"\n✅ Total documents loaded: {len(all_documents)}\n")
    return all_documents

# Load all documents from CSV and PDF files
documents = load_documents_from_folder(documents_folder_path)

if not documents:
    print("❌ No documents loaded. Please check your folder path and files.")
    exit()

# 🧠 Create embeddings and FAISS vector store
print("🧠 Creating embeddings and FAISS vector store...")
embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
embedding = HuggingFaceEmbeddings(model_name=embedding_model)

# Create FAISS vector store from documents
vector_store = FAISS.from_documents(documents, embedding)
print("✅ FAISS vector store created successfully\n")

faiss_index_path = "faiss_index"
vector_store.save_local(faiss_index_path)
print(f"💾 FAISS index saved to {faiss_index_path}\n")

faiss_index_path = "faiss_index"
vector_store = FAISS.load_local(
    faiss_index_path, 
    embedding,
    allow_dangerous_deserialization=True
)
print(f"📥 FAISS index loaded from {faiss_index_path}\n")


# ✅ Use built-in retriever
# You can customize the retriever with search_kwargs
retriever = vector_store.as_retriever(
    search_type="similarity",  # or "mmr" for Maximum Marginal Relevance
    search_kwargs={"k": 4}  # Number of documents to retrieve
)

# Use Ollama LLaMA 3.2 model
print("🤖 Initializing Ollama LLM...")
llm = OllamaLLM(model="gemma3:4b", base_url="http://localhost:11434")
print("✅ LLM initialized\n")

# 🧠 Prompt template
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """Please utilize the data from the CSV and PDF files to extract relevant information and insights in response to the user's inquiries. 
        The analysis should include identifying patterns, summarizing key statistics, and generating accurate, coherent, and tailored responses to the user's questions. 
        Ensure that the output maintains precision, contextual awareness, and clarity, incorporating explanations. 
        When relevant, mention which file the information comes from (check the source_file and file_type in the metadata).
        If a question is not directly related to the provided data, kindly indicate that the inquiry is unrelated.
        
Context from CSV and PDF files:
{context}"""
    ),
    ("human", "{input}")
])

# 🔁 Build the document QA chain
stuff_chain = create_stuff_documents_chain(llm, prompt)
qa_chain = create_retrieval_chain(retriever, stuff_chain)

# 💬 Interactive query loop
print("=" * 60)
print("🚀 Multi-Format Question Answering System Ready!")
print("   Supports: CSV files and PDF documents")
print("   Vector Store: FAISS")
print("=" * 60)
print("Type 'quit', 'exit', or 'q' to stop\n")

while True:
    question = input("🙋 Your question: ").strip()
    
    if question.lower() in ['quit', 'exit', 'q', '']:
        print("\n👋 Goodbye!")
        break
    
    print("\n🔍 Processing your question...\n")
    
    try:
        response = qa_chain.invoke({"input": question})
        
        # 🖨️ Output the answer
        print("-" * 60)
        print("🤖 Bot:", response["answer"])
        print("-" * 60)
        
        # Optional: Show source documents
        if "context" in response:
            print("\n📚 Source files used:")
            source_files = {}
            for doc in response["context"]:
                if 'source_file' in doc.metadata:
                    file_name = doc.metadata['source_file']
                    file_type = doc.metadata.get('file_type', 'Unknown')
                    source_files[file_name] = file_type
            
            for source, ftype in source_files.items():
                print(f"   • {source} ({ftype})")
        print("\n")
        
    except Exception as e:
        print(f"❌ Error processing question: {str(e)}\n")
