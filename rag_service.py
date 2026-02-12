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

retriever = vector_store.as_retriever(search_kwargs={"k": 5})  # Increased to get more context


def get_rag_context(query: str, exclude_account: str = None) -> str:
    """
    Get RAG context for explanation and formatting
    
    Args:
        query: The user's question
        exclude_account: Account ID to exclude (to avoid showing user their own data from docs)
    """
    docs = retriever.invoke(query)

    if not docs:
        return ""

    # Filter out documents from the user's own account if specified
    if exclude_account:
        exclude_str = str(exclude_account)
        filtered_docs = [d for d in docs if exclude_str not in d.page_content]
    else:
        filtered_docs = docs

    if not filtered_docs:
        return ""

    context = "\n\n".join(
        f"REFERENCE MATERIAL (FOR EXPLANATION ONLY - NOT YOUR DATA):\n{d.page_content[:500]}"
        for d in filtered_docs[:3]  # Limit to top 3 to avoid token overflow
    )
    
    return context


def get_insights_from_other_customers(user_account_id: int, query_type: str = "general") -> str:
    """
    Get insights based on other customers' transaction patterns

    Args:
        user_account_id: Current user's account ID (to exclude their own docs)
        query_type: Type of insight needed
    """

    # Richer, more specific queries per type
    insight_queries = {
        "investment": [
            "investment products mutual funds stocks bonds",
            "customers investing equity fixed deposit SIP",
            "popular financial products high returns"
        ],
        "spending":   [
            "spending patterns categories expenses monthly",
            "customer spending groceries utilities bills",
            "top expense categories transactions"
        ],
        "savings":    [
            "savings strategies high interest accounts",
            "customer savings growth recurring deposit",
            "best savings plans financial growth"
        ],
        "general":    [
            "customer transactions investment spending overview",
            "financial patterns trends across accounts"
        ]
    }

    queries = insight_queries.get(query_type, insight_queries["general"])
    user_account_str = str(user_account_id)

    all_docs = []
    seen_content = set()

    for query in queries:
        docs = retriever.invoke(query)
        for doc in docs:
            # Exclude current user's documents
            if user_account_str not in doc.page_content:
                # Deduplicate by content snippet
                snippet = doc.page_content[:80]
                if snippet not in seen_content:
                    seen_content.add(snippet)
                    all_docs.append(doc)

    if not all_docs:
        return ""

    # Build a rich insights context (up to 6 docs for better coverage)
    insights = f"CUSTOMER DATA FOR INSIGHTS ({query_type.upper()}):\n\n"
    for i, doc in enumerate(all_docs[:6], 1):
        source = doc.metadata.get("source", "unknown")
        insights += f"--- Customer Record {i} (Source: {source}) ---\n"
        insights += f"{doc.page_content[:600]}\n\n"

    return insights


def get_combined_context(
    user_question: str,
    user_account_id: int,
    include_insights: bool = True,
    insight_type: str = "general"
) -> dict:
    """
    Get combined RAG context including explanations and insights
    
    Returns:
        dict with 'explanation' and 'insights' keys
    """
    
    # Get explanatory context (exclude user's own documents)
    explanation_context = get_rag_context(user_question, exclude_account=user_account_id)
    
    # Get insights from other customers
    insights_context = ""
    if include_insights:
        insights_context = get_insights_from_other_customers(user_account_id, insight_type)
    
    return {
        "explanation": explanation_context,
        "insights": insights_context
    }