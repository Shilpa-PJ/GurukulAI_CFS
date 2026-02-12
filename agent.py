from langchain_ollama import OllamaLLM
from tool_executor import execute_tool
import json
import re

# Import RAG service
try:
    from rag_service import get_combined_context, get_insights_from_other_customers
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠️ RAG service not available")

llm = OllamaLLM(
    model="gemma3:4b",
    base_url="http://localhost:11434"
)

MAX_ITERATIONS = 3


# ─────────────────────────────────────────────
# UTILITY: Mask account numbers in any data
# ─────────────────────────────────────────────
def mask_account_in_data(data, account_id):
    account_str = str(account_id)
    masked = "*" * (len(account_str) - 4) + account_str[-4:]

    if isinstance(data, dict):
        return {k: mask_account_in_data(v, account_id) for k, v in data.items()}
    elif isinstance(data, list):
        return [mask_account_in_data(item, account_id) for item in data]
    elif isinstance(data, str):
        return data.replace(account_str, masked)
    elif isinstance(data, int) and data == account_id:
        return masked
    return data


# ─────────────────────────────────────────────
# GUARD 1: Banking topic filter
# ─────────────────────────────────────────────
def is_banking_related(question: str):
    check_prompt = f"""
You are a banking assistant filter. Determine if this question is related to banking services.

Question: "{question}"

Banking-related topics include:
- Account balances, transactions, bank statements
- Deposits, withdrawals, account information
- Banking services, financial transactions

NOT banking-related:
- General knowledge, current events, politics
- Entertainment, personal advice (non-financial)
- Technical support (non-banking)

Respond in JSON format:
{{
  "is_banking": true/false,
  "reason": "brief explanation"
}}
"""
    response = llm.invoke(check_prompt).strip()
    if response.startswith("```json"):
        response = response.split("```json")[1].split("```")[0].strip()
    elif response.startswith("```"):
        response = response.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(response)
        return result.get("is_banking", False), result.get("reason", "")
    except:
        banking_keywords = [
            'account', 'balance', 'transaction', 'deposit', 'withdraw',
            'statement', 'payment', 'transfer', 'money', 'banking',
            'credit', 'debit', 'funds', 'spending', 'savings'
        ]
        is_banking = any(k in question.lower() for k in banking_keywords)
        return is_banking, "Keyword-based detection"


# ─────────────────────────────────────────────
# GUARD 2: Account access check
# ─────────────────────────────────────────────
def check_account_access(user_question: str, user_account_id: int, masked_account: str):
    # Check for explicit account numbers (8-12 digits)
    mentioned_accounts = re.findall(r'\b\d{8,12}\b', user_question)
    for mentioned_account in mentioned_accounts:
        if int(mentioned_account) != user_account_id:
            return False, f"Access denied. You can only view information for your account ({masked_account}). You cannot access account {mentioned_account}."

    # Check for contextual patterns like "account 123"
    account_patterns = [
        r'account\s+(?:number\s+)?(\d+)',
        r'account\s+id\s+(\d+)',
        r'for\s+account\s+(\d+)',
        r'balance\s+for\s+(\d+)',
    ]
    for pattern in account_patterns:
        for match in re.findall(pattern, user_question.lower()):
            if match.isdigit() and len(match) >= 4 and int(match) != user_account_id:
                return False, f"Access denied. You can only view information for your account ({masked_account}). You cannot access account {match}."

    return True, None


# ─────────────────────────────────────────────
# INSIGHTS: Generate market comparison
# ─────────────────────────────────────────────
def get_market_insights(user_account_id: int, user_question: str = "") -> str:
    if not RAG_AVAILABLE:
        return "Insights are currently unavailable. Please try again later."

    try:
        # Fetch all three categories for richer data
        investment_data = get_insights_from_other_customers(user_account_id, "investment")
        spending_data   = get_insights_from_other_customers(user_account_id, "spending")
        savings_data    = get_insights_from_other_customers(user_account_id, "savings")

        combined_data = f"""
INVESTMENT PATTERNS FROM OTHER CUSTOMERS:
{investment_data if investment_data else "No investment data available."}

SPENDING PATTERNS FROM OTHER CUSTOMERS:
{spending_data if spending_data else "No spending data available."}

SAVINGS PATTERNS FROM OTHER CUSTOMERS:
{savings_data if savings_data else "No savings data available."}
"""

        insight_prompt = f"""
You are a financial advisor for FirstNet Investor.

Analyze the anonymized transaction and statement data from other customers below and provide
clear, structured, and actionable insights to help this customer improve their profit
and investment decisions.

Customer Data from Other Accounts (Anonymized):
{combined_data}

Generate a detailed response covering EXACTLY these 5 sections:

1. 📈 TOP INVESTED PRODUCTS
   - List the top 3-5 products/categories most customers are investing in
   - Include approximate percentage of customers investing in each

2. 💹 MARKET TRENDS
   - What financial trends are observed across customers
   - Which sectors/products are growing in popularity

3. 🏆 BEST PERFORMING CATEGORIES
   - Which investment categories are yielding the best returns
   - Include any specific products with notable performance

4. 💡 PERSONALIZED RECOMMENDATIONS
   - Specific steps this customer can take to improve profit
   - Suggest 2-3 actionable investment moves based on what others are doing

5. ⚠️ RISK CONSIDERATIONS
   - Any risks or market volatility to be aware of
   - Diversification suggestions

IMPORTANT RULES:
- DO NOT reveal any specific account numbers or personal details
- Base insights ONLY on the data provided above
- Be specific with product names, percentages, and figures where available
- Keep the tone professional and encouraging
"""

        response = llm.invoke(insight_prompt)
        print(f"✅ Market insights generated successfully")
        return response

    except Exception as e:
        print(f"❌ Error generating insights: {e}")
        import traceback
        traceback.print_exc()
        return "I encountered an error while fetching market insights. Please try again."


# ─────────────────────────────────────────────
# MAIN AGENT
# ─────────────────────────────────────────────
def run_agent(user_question: str, user_account_id: int, username: str, max_iterations: int = MAX_ITERATIONS):
    masked_account = "*" * (len(str(user_account_id)) - 4) + str(user_account_id)[-4:]

    # ── STEP 1: Handle "Yes" to insights immediately ──────────────────────────
    yes_responses = [
        'yes', 'yeah', 'sure', 'ok', 'okay', 'please', 'yep', 'y',
        'yes please', 'yes sure', 'yes i want', 'yes i would like',
        'yes show me', 'show me insights', 'yes insights'
    ]
    if user_question.strip().lower() in yes_responses:
        print(f"💡 User confirmed insights - generating market comparison...")
        insights = get_market_insights(user_account_id, user_question)
        return {
            "type": "answer",
            "response": insights,
            "iterations": 1,
            "tools_used": [],
            "has_documents": False,
            "insights_included": True,
            "ask_insights": False
        }

    # ── STEP 2: Handle "No" to insights immediately ───────────────────────────
    no_responses = ['no', 'nope', 'no thanks', 'no thank you', 'not now', 'skip', 'n']
    if user_question.strip().lower() in no_responses:
        return {
            "type": "answer",
            "response": "No problem! Feel free to ask me anything else about your account.",
            "iterations": 1,
            "tools_used": [],
            "has_documents": False,
            "insights_included": False,
            "ask_insights": False
        }

    # ── STEP 3: Banking topic filter ─────────────────────────────────────────
    print(f"🔍 Checking if question is banking-related...")
    is_banking, reason = is_banking_related(user_question)
    print(f"Banking check: {is_banking} - {reason}")

    if not is_banking:
        return {
            "type": "error",
            "response": "I'm a banking assistant and can only help with banking-related queries such as account balances, transactions, and statements. Please ask me about your banking needs.",
            "iterations": 0
        }

    # ── STEP 4: Account access check ─────────────────────────────────────────
    is_valid, error_msg = check_account_access(user_question, user_account_id, masked_account)
    if not is_valid:
        return {
            "type": "error",
            "response": error_msg,
            "iterations": 0
        }

    # ── STEP 5: Statement / document request shortcut ─────────────────────────
    statement_keywords = [
        'statement', 'document', 'download', 'pdf',
        'annual statement', 'monthly statement', 'periodic statement'
    ]
    if any(kw in user_question.lower() for kw in statement_keywords):
        print(f"📄 Detected statement/document request - providing direct answer")
        return {
            "type": "answer",
            "response": "I've found your account statements. Please see the available documents below for download.",
            "iterations": 1,
            "tools_used": [],
            "has_documents": True,
            "insights_included": False,
            "ask_insights": False
        }

    # ── STEP 6: Agentic loop ─────────────────────────────────────────────────
    conversation_history = [{"role": "user", "content": user_question}]
    iteration = 0

    print(f"\n{'='*60}")
    print(f"🤖 AGENT STARTED | User: {username} | Account: {masked_account}")
    print(f"Question: {user_question}")
    print(f"{'='*60}\n")

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        # Build context for LLM (masked account only)
        context = f"[User: {username}, AccountID: {masked_account}]\n"
        context += f"Original Question: {user_question}\n\n"

        if len(conversation_history) > 1:
            context += "Previous steps:\n"
            for i, msg in enumerate(conversation_history[1:], 1):
                preview = str(msg['content'])[:100].replace(str(user_account_id), masked_account)
                context += f"{i}. {msg['role']}: {preview}...\n"

        decision_prompt = f"""
{context}

Based on the conversation so far, decide what to do next.

Available tools: get_account_balance, get_transaction_history, get_periodic_statements, get_adhoc_statements

Think step by step:
- Have I gathered all the information needed?
- Do I need to call any more tools?
- Can I provide a complete answer now?

Respond ONLY in JSON format:
{{
  "reasoning": "explain your thinking",
  "action": "tool" or "answer" or "clarify",
  "tool_name": "tool name if action is tool, else null",
  "tool_args": {{}},
  "response": "your answer if action is answer or clarify, else null"
}}

NOTE: Do NOT include account_id in tool_args - it will be injected automatically.
"""

        print(f"🤔 Agent thinking...")
        decision_response = llm.invoke(decision_prompt)
        print(f"💭 Decision: {decision_response[:200]}...")

        # Parse JSON decision
        try:
            decision_response = decision_response.strip()
            if decision_response.startswith("```json"):
                decision_response = decision_response.split("```json")[1].split("```")[0].strip()
            elif decision_response.startswith("```"):
                decision_response = decision_response.split("```")[1].split("```")[0].strip()

            decision = json.loads(decision_response)
            print(f"📋 Action: {decision.get('action')}")
            print(f"🧠 Reasoning: {decision.get('reasoning', '')[:100]}")

        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse decision: {e}")
            if iteration >= 2:
                return {
                    "type": "partial_answer",
                    "response": "I'm having trouble processing this request. Please try rephrasing your question.",
                    "iterations": iteration,
                    "ask_insights": False
                }
            return {
                "type": "answer",
                "response": decision_response,
                "iterations": iteration,
                "ask_insights": False
            }

        action = decision.get("action", "answer")

        # ── Tool call ────────────────────────────────────────────────────────
        if action == "tool":
            tool_name = decision.get("tool_name")
            tool_args = decision.get("tool_args", {})
            tool_args["account_id"] = user_account_id  # Always force user's own account

            print(f"🔧 Calling tool: {tool_name} with args: {tool_args}")
            try:
                tool_result = execute_tool(tool_name, tool_args)
                print(f"✅ Tool result: {str(tool_result)[:100]}...")
                masked_result = mask_account_in_data(tool_result, user_account_id)
                conversation_history.append({
                    "role": "tool",
                    "tool": tool_name,
                    "content": json.dumps(masked_result, indent=2)
                })
            except Exception as e:
                print(f"❌ Tool failed: {e}")
                conversation_history.append({
                    "role": "error",
                    "content": f"Tool {tool_name} failed: {str(e)}"
                })

        # ── Final answer ─────────────────────────────────────────────────────
        elif action == "answer":
            print(f"✅ Providing final answer")

            asking_for_documents = any(kw in user_question.lower() for kw in [
                'download', 'statement', 'document', 'pdf', 'file'
            ])

            # Get RAG explanation context
            rag_explanation = ""
            if RAG_AVAILABLE:
                try:
                    ctx = get_combined_context(
                        user_question=user_question,
                        user_account_id=user_account_id,
                        include_insights=False
                    )
                    rag_explanation = ctx.get("explanation", "")
                    print(f"📚 RAG context retrieved")
                except Exception as e:
                    print(f"⚠️ RAG retrieval failed: {e}")

            final_prompt = f"""
You are a banking assistant for FirstNet Investor. Answer the user's question.

PRIORITY: Use tool results as your ONLY source of facts.
Reference material below is for explanation only - never use it as data.

User Question: {user_question}

Tool Results (AUTHORITATIVE DATA):
{json.dumps(conversation_history, indent=2)}

{f"Reference Material (explanation only):{chr(10)}{rag_explanation}" if rag_explanation else ""}

INSTRUCTIONS:
- Answer using ONLY the tool results above
- Be clear, professional, and concise
- Format currency properly (e.g., $1,234.56)
- Use masked account format as shown in the data
- Do NOT make up any figures

Answer:
"""
            final_answer = llm.invoke(final_prompt)

            # Ask about insights if a tool was used
            tool_names = [m.get("tool") for m in conversation_history if m.get("role") == "tool"]
            should_ask_insights = len(tool_names) > 0

            return {
                "type": "answer",
                "response": final_answer,
                "iterations": iteration,
                "tools_used": [m for m in conversation_history if m.get("role") == "tool"],
                "has_documents": asking_for_documents,
                "insights_included": False,
                "ask_insights": should_ask_insights
            }

        # ── Clarification ────────────────────────────────────────────────────
        elif action == "clarify":
            return {
                "type": "clarify",
                "response": decision.get("response", "Could you please provide more details?"),
                "iterations": iteration,
                "ask_insights": False
            }

        else:
            return {
                "type": "answer",
                "response": decision.get("response", "I'm not sure how to help with that."),
                "iterations": iteration,
                "ask_insights": False
            }

    # ── Max iterations fallback ───────────────────────────────────────────────
    print(f"⚠️ Max iterations ({max_iterations}) reached")
    gathered = [f"- Called {m.get('tool')}" for m in conversation_history if m.get("role") == "tool"]

    fallback_prompt = f"""
You are a banking assistant. Answer as best you can given what was retrieved.

User's question: {user_question}

Data gathered:
{chr(10).join(gathered) if gathered else "- No data retrieved"}

Full history:
{json.dumps(conversation_history, indent=2)}

Provide the best answer possible. If incomplete, say so and suggest the user rephrase.
"""
    try:
        final_answer = llm.invoke(fallback_prompt)
    except Exception as e:
        print(f"❌ Fallback error: {e}")
        final_answer = "I hit a processing limit. Please try rephrasing your question or ask something more specific."

    return {
        "type": "partial_answer",
        "response": final_answer,
        "iterations": iteration,
        "note": "Maximum iterations reached. This may be a partial answer.",
        "ask_insights": False
    }


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def run_simple_agent(user_question: str, user_account_id: int, username: str):
    analysis_prompt = f"""
Analyze this banking question: "{user_question}"

Does this require multiple pieces of information or calculations?

Respond in JSON:
{{
  "is_complex": true/false,
  "steps": ["step 1", "step 2"],
  "tools_needed": ["tool1", "tool2"]
}}
"""
    analysis = llm.invoke(analysis_prompt)
    print(f"📊 Question Analysis: {analysis}")

    return run_agent(user_question, user_account_id, username)