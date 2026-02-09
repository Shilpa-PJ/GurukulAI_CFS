from langchain_ollama import OllamaLLM
import json

llm = OllamaLLM(
    model="gemma3:4b",
    base_url="http://localhost:11434"
)

def summarize(tool_name, tool_result, rag_context, user_question):
    # Convert tool_result to a clean, readable JSON string
    if isinstance(tool_result, dict):
        tool_result_str = json.dumps(tool_result, indent=2, ensure_ascii=False)
    else:
        tool_result_str = str(tool_result)
    
    # Debug: Print what we're sending to the LLM
    print(f"🔍 Tool result being sent to LLM:\n{tool_result_str}")
    
    prompt = f"""
You are a banking assistant.

CRITICAL RULES:
1. ALL factual information (account numbers, balances, dates, amounts, transactions)
   MUST come ONLY from the Tool Data below.
2. The Tool Data contains the ACTUAL facts from the database - use this information.
3. Reference material is for explanation or formatting ONLY - DO NOT take factual data from it.
4. NEVER invent, guess, or copy values from reference material.
5. If a value is missing in the Tool Data, say: "This information is not available."
6. If the question is unrelated to banking, reply: "Sorry, I can only help with banking-related queries."

User Question:
{user_question}

Tool Data (USE THIS - THIS IS THE REAL DATA):
{tool_result_str}

Reference Material (FOR CONTEXT ONLY - NOT FOR DATA):
{rag_context}

Instructions:
- Read the Tool Data carefully
- Extract the relevant information from the Tool Data
- Answer the user's question using ONLY the data from Tool Data
- Be clear, professional, and concise
- Format currency amounts properly (e.g., $1,234.56)

Answer:
"""

    response = llm.invoke(prompt)
    print(f"🤖 LLM Response: {response}")
    return response