from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from langchain_ollama import OllamaLLM
# RAG is now used inside agent.py, not here
# from rag_service import get_rag_context

from planner import plan_tool_call
#from mcp_client import call_mcp_tool
from summarizer import summarize
from tool_executor import execute_tool
from agent import run_simple_agent  # Import the agent
import sqlite3
from typing import Optional
import secrets
from pathlib import Path
import os

import json

DB_NAME = "AIGurukul.db"
DOCS_DIR = Path("Account_docs")  # Directory containing customer documents

'''from mcp_tools import (
    get_account_balance,
    get_transaction_history,
    get_adhoc_statements,
    get_periodic_statements,
)



tools = [
    get_account_balance,
    get_transaction_history,
    get_adhoc_statements,
    get_periodic_statements,
]'''

app = FastAPI()

llm = OllamaLLM(
    model="gemma3:4b",
    base_url="http://localhost:11434"
)

# Session storage: {token: {"username": str, "accountId": int}}
active_sessions = {}

# Allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    token: str  # Session token to identify the logged-in user

class ChatResponse(BaseModel):
    response: str

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def mask_account_number(account_id):
    """Mask account number to show only last 4 digits"""
    account_str = str(account_id)
    if len(account_str) <= 4:
        return account_str
    return "*" * (len(account_str) - 4) + account_str[-4:]

def mask_account_numbers_in_result(data, account_id):
    """Recursively mask account numbers in the tool result"""
    if isinstance(data, dict):
        masked_data = {}
        for key, value in data.items():
            if key in ["accountId", "account_id", "account", "accountNumber"]:
                masked_data[key] = mask_account_number(value)
            else:
                masked_data[key] = mask_account_numbers_in_result(value, account_id)
        return masked_data
    elif isinstance(data, list):
        return [mask_account_numbers_in_result(item, account_id) for item in data]
    elif isinstance(data, (int, str)) and str(data) == str(account_id):
        return mask_account_number(data)
    else:
        return data

def find_statement_files(account_id: int, statement_type: str = "all") -> list:
    """
    Find statement files for a given account
    
    Args:
        account_id: The account ID
        statement_type: "monthly", "annual", or "all"
    
    Returns:
        List of dicts with file info: {name, path, type, size}
    """
    files = []
    account_str = str(account_id)
    
    if not DOCS_DIR.exists():
        print(f"⚠️ Documents directory not found: {DOCS_DIR}")
        return files
    
    # Search patterns - make more flexible
    patterns = []
    
    if statement_type == "monthly" or statement_type == "all":
        patterns.extend([
            f"*{account_str}*monthly*.pdf",
            f"*{account_str}*month*.pdf",
            f"{account_str}_monthly*.pdf",
            f"{account_str}_month*.pdf"
        ])
    
    if statement_type == "annual" or statement_type == "all":
        patterns.extend([
            f"*{account_str}*annual*.pdf",
            f"*{account_str}*yearly*.pdf",
            f"*{account_str}*year*.pdf",
            f"{account_str}_annual*.pdf",
            f"{account_str}_year*.pdf"
        ])
    
    if statement_type == "all":
        patterns.extend([
            f"*{account_str}*statement*.pdf",
            f"{account_str}_statement*.pdf",
            f"{account_str}*.pdf"
        ])
    
    seen_files = set()
    
    for pattern in patterns:
        matching_files = list(DOCS_DIR.glob(pattern))
        print(f"🔍 Pattern '{pattern}' found {len(matching_files)} files")
        
        for file_path in matching_files:
            if file_path.name not in seen_files:
                seen_files.add(file_path.name)
                
                # Determine file type
                name_lower = file_path.name.lower()
                if "month" in name_lower and "annual" not in name_lower:
                    file_type = "monthly"
                elif "annual" in name_lower or "yearly" in name_lower or "year" in name_lower:
                    file_type = "annual"
                elif "statement" in name_lower:
                    file_type = "statement"
                else:
                    file_type = "document"
                
                files.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "type": file_type,
                    "size": file_path.stat().st_size,
                    "download_url": f"/api/download/{file_path.name}"
                })
    
    print(f"📄 Found {len(files)} total files for account {account_str}")
    return files

def get_user_from_db(username: str, password: str):
    """Fetch user details from UserDetails table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT username, password, accountId
        FROM UserDetails
        WHERE username = ? AND password = ?
    """, (username, password))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_session_user(token: str) -> Optional[dict]:
    """Get user info from active session"""
    return active_sessions.get(token)

# ---- Routes ----
@app.post("/login")
def login(req: LoginRequest):
    # Authenticate user from database
    user = get_user_from_db(req.username, req.password)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate session token
    token = secrets.token_urlsafe(32)
    
    # Store session with accountId (full number for internal use)
    active_sessions[token] = {
        "username": user["username"],
        "accountId": user["accountId"]
    }
    
    return {
        "status": "success",
        "token": token,
        "username": user["username"],
        "accountId": user["accountId"],  # Full number for internal use
        "maskedAccountId": mask_account_number(user["accountId"])  # Masked for display
    }

@app.post("/logout")
def logout(token: str):
    """Logout and clear session"""
    if token in active_sessions:
        del active_sessions[token]
    return {"status": "logged out"}

# ADDED THIS NEW ENDPOINT HERE
@app.get("/welcome")
def get_welcome_message():
    return {
        "message": "Hi, I am your banking assistant. How can I help you today?",
        "status": "ready"
    }

# New endpoint for getting insights
@app.post("/insights")
def get_insights(req: ChatRequest):
    """Get personalized insights based on other customers' data"""
    user_session = get_session_user(req.token)
    if not user_session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    
    try:
        from rag_service import get_insights_from_other_customers
        
        user_account_id = user_session["accountId"]
        insights = get_insights_from_other_customers(user_account_id, "general")
        
        return {"insights": insights}
    except ImportError:
        return {"insights": "Insights feature not available. Please set up RAG service."}
    except Exception as e:
        return {"insights": f"Error retrieving insights: {str(e)}"}

# New endpoint for listing available documents
@app.get("/api/statements/{account}/files")
def list_statement_files(account: int, token: str):
    """List available statement files for an account"""
    user_session = get_session_user(token)
    if not user_session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    
    # Verify user is requesting their own account
    if user_session["accountId"] != account:
        raise HTTPException(status_code=403, detail="Access denied.")
    
    files = find_statement_files(account)
    return {
        "accountId": account,
        "files": files,
        "count": len(files)
    }

# New endpoint for downloading files
@app.get("/api/download/{filename}")
def download_file(filename: str, token: str):
    """Download a statement file"""
    user_session = get_session_user(token)
    if not user_session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    
    # Security: Verify filename contains user's account ID
    user_account_id = str(user_session["accountId"])
    if user_account_id not in filename:
        raise HTTPException(status_code=403, detail="Access denied. This file doesn't belong to your account.")
    
    # Prevent directory traversal attacks
    filename = os.path.basename(filename)
    file_path = DOCS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Invalid file.")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/pdf'
    )

# 1️⃣ Account Balance - Now requires authentication
@app.get("/api/accounts/{account}/balance")
def get_account_balance_api(account: int):
    """Direct API endpoint - public for now"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT accountId, balanceAmount, currency, asOfDate
        FROM AccountBalance
        WHERE accountId = ?
        ORDER BY asOfDate DESC
        LIMIT 1
    """, (account,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    return dict(row)

# 3️⃣ Transaction History
@app.get("/api/accounts/{account}/transactions")
def get_transaction_history_api(account: int):
    """Direct API endpoint - public for now"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT transactionId, date, description, netAmount, type, "balance After"
        FROM TransactionHistory
        WHERE accountId = ?
        ORDER BY date DESC
    """, (account,))

    rows = cursor.fetchall()
    conn.close()

    return {
        "accountId": account,
        "transactions": [dict(row) for row in rows]
    }

# 4️⃣ AdHoc Statements
@app.get("/api/accounts/{account}/statements/adhoc")
def get_adhoc_statements_api(account: int):
    """Direct API endpoint - public for now"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT statementId, startDate, endDate, requestId,
               submittedByRole, requestTimestamp
        FROM AdHocStatement
        WHERE accountId = ?
        ORDER BY requestTimestamp DESC
    """, (account,))

    rows = cursor.fetchall()
    conn.close()

    return {
        "accountId": account,
        "adhocStatements": [dict(row) for row in rows]
    }

FINAL_ANSWER_PROMPT = """
You are a banking assistant.

CRITICAL RULES:
1. ALL factual information (names, balances, dates, amounts, transactions)
   MUST come ONLY from the tool response.
2. The reference documents are for explanation or formatting ONLY.
3. If a value is missing in the tool response, say:
   "This information is not available."
4. NEVER infer, guess, or copy data from reference documents.
5. If reference content conflicts with tool data, IGNORE the reference.

Tool Response (FACTS):
{tool_data}

Reference Material (DO NOT USE AS DATA):
{rag_context}

User Question:
{question}

Answer clearly and professionally.
"""

# 5️⃣ Periodic (Current) Statements
@app.get("/api/accounts/{account}/statements/current")
def get_periodic_statements_api(
    account: int,
    periodStartDate: Optional[str] = None,
    periodEndDate: Optional[str] = None
):
    """Direct API endpoint - public for now"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build query with optional date filters
    query = """
        SELECT accountId, periodStartDate, periodEndDate, OpeningBalance, ClosingBalance
        FROM PeriodicStatement
        WHERE accountId = ?
    """
    params = [account]
    
    if periodStartDate:
        query += " AND periodStartDate >= ?"
        params.append(periodStartDate)
    
    if periodEndDate:
        query += " AND periodEndDate <= ?"
        params.append(periodEndDate)
    
    query += " ORDER BY periodEndDate DESC"
    
    cursor.execute(query, params)

    rows = cursor.fetchall()
    conn.close()

    return {
        "accountId": account,
        "periodicStatements": [dict(row) for row in rows]
    }

from tool_executor import execute_tool

@app.post("/chat")
def chat(req: ChatRequest):
    # Verify session
    user_session = get_session_user(req.token)
    if not user_session:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please login again.")
    
    # Get user's accountId
    user_account_id = user_session["accountId"]
    username = user_session["username"]
    masked_account = mask_account_number(user_account_id)
    
    print(f"\n{'='*60}")
    print(f"💬 NEW CHAT REQUEST")
    print(f"User: {username} | Account: {masked_account}")
    print(f"Question: {req.message}")
    print(f"{'='*60}\n")
    
    # Use the agentic system
    try:
        result = run_simple_agent(
            user_question=req.message,
            user_account_id=user_account_id,
            username=username
        )
        
        print(f"\n{'='*60}")
        print(f"🎯 AGENT COMPLETED")
        print(f"Type: {result['type']}")
        print(f"Iterations: {result.get('iterations', 0)}")
        if 'tools_used' in result:
            print(f"Tools used: {[t['tool'] for t in result['tools_used']]}")
        if 'note' in result:
            print(f"Note: {result['note']}")
        print(f"{'='*60}\n")
        
        # Get response text
        response_text = result.get("response", "I couldn't process your request.")
        
        # Add note if partial answer
        if result.get('type') == 'partial_answer' and result.get('note'):
            response_text += f"\n\n_Note: {result['note']}_"
        
        # Mask account numbers in response
        response_text = response_text.replace(str(user_account_id), masked_account)
        
        # Append insight prompt if applicable
        if result.get("ask_insights", False):
            response_text += "\n\n---\n💡 **Would you like insights on your account by comparing to market trends on how to improve your profit and investment?**"
        
        # Check if documents are available
        documents = []
        if result.get('has_documents', False):
            # Determine what type of statement is being requested
            statement_type = "all"
            if "annual" in req.message.lower() or "yearly" in req.message.lower():
                statement_type = "annual"
            elif "monthly" in req.message.lower() or "month" in req.message.lower():
                statement_type = "monthly"
            
            documents = find_statement_files(user_account_id, statement_type)
            
            # Enhance response if documents found
            if documents:
                doc_count = len(documents)
                response_text += f"\n\n📄 I found {doc_count} document{'s' if doc_count != 1 else ''} for you. Click the download button{'s' if doc_count != 1 else ''} below to access your statement{'s' if doc_count != 1 else ''}."
            else:
                response_text += f"\n\n⚠️ I couldn't find any statement documents in our system. Please contact support if you believe this is an error."
        
        return {
            "response": response_text,
            "documents": documents if documents else None
        }
        
    except Exception as e:
        print(f"❌ Agent error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "response": "I encountered an error processing your request. Please try again or rephrase your question.",
            "documents": None
        }