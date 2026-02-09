from langchain_ollama import OllamaLLM
from planner import plan_tool_call
from tool_executor import execute_tool
import json

llm = OllamaLLM(
    model="gemma3:4b",
    base_url="http://localhost:11434"
)

MAX_ITERATIONS = 5  # Prevent infinite loops

def mask_account_in_data(data, account_id):
    """Mask account ID in any data structure"""
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
    else:
        return data

def is_banking_related(question: str):
    """
    Check if the question is banking-related
    Returns: (is_banking, explanation)
    """
    check_prompt = f"""
You are a banking assistant filter. Determine if this question is related to banking services.

Question: "{question}"

Banking-related topics include:
- Account balances
- Transactions
- Bank statements
- Deposits and withdrawals
- Account information
- Banking services
- Financial transactions in the user's account

NOT banking-related:
- General knowledge questions
- Current events
- Politics
- Entertainment
- Personal advice (non-financial)
- Technical support (non-banking)
- Any topic outside of personal banking

Respond in JSON format:
{{
  "is_banking": true/false,
  "reason": "brief explanation"
}}
"""
    
    response = llm.invoke(check_prompt).strip()
    
    # Clean JSON response
    if response.startswith("```json"):
        response = response.split("```json")[1].split("```")[0].strip()
    elif response.startswith("```"):
        response = response.split("```")[1].split("```")[0].strip()
    
    try:
        result = json.loads(response)
        return result.get("is_banking", False), result.get("reason", "")
    except:
        # If parsing fails, use simple keyword check as fallback
        banking_keywords = [
            'account', 'balance', 'transaction', 'deposit', 'withdraw',
            'statement', 'payment', 'transfer', 'money', 'banking',
            'credit', 'debit', 'funds', 'spending', 'savings'
        ]
        question_lower = question.lower()
        is_banking = any(keyword in question_lower for keyword in banking_keywords)
        return is_banking, "Keyword-based detection"


def check_account_access(user_question: str, user_account_id: int, masked_account: str):
    """
    Check if user is trying to access a different account
    Returns: (is_valid, error_message)
    """
    import re
    
    # Pattern 1: Check for explicit account numbers in the question
    mentioned_accounts = re.findall(r'\b\d{8,12}\b', user_question)  # 8-12 digit numbers
    for mentioned_account in mentioned_accounts:
        if int(mentioned_account) != user_account_id:
            return False, f"Access denied. You can only view information for your account ({masked_account}). You cannot access account {mentioned_account}."
    
    # Pattern 2: Check for phrases like "account 123", "account number 456"
    account_patterns = [
        r'account\s+(?:number\s+)?(\d+)',
        r'account\s+id\s+(\d+)',
        r'for\s+account\s+(\d+)',
        r'balance\s+for\s+(\d+)',
    ]
    
    for pattern in account_patterns:
        matches = re.findall(pattern, user_question.lower())
        for match in matches:
            if match.isdigit() and len(match) >= 4 and int(match) != user_account_id:
                return False, f"Access denied. You can only view information for your account ({masked_account}). You cannot access account {match}."
    
    # If no suspicious patterns found, allow access
    # Don't use LLM detection as it's too unreliable
    return True, None


def run_agent(user_question: str, user_account_id: int, username: str, max_iterations: int = MAX_ITERATIONS):
    """
    Agentic loop that can make multiple tool calls to answer complex questions
    """
    
    # Create masked version for display to LLM
    masked_account = "*" * (len(str(user_account_id)) - 4) + str(user_account_id)[-4:]
    
    # FIRST: Check if question is banking-related
    print(f"🔍 Checking if question is banking-related...")
    is_banking, reason = is_banking_related(user_question)
    print(f"Banking check: {is_banking} - {reason}")
    
    if not is_banking:
        return {
            "type": "error",
            "response": "I'm a banking assistant and can only help with banking-related queries such as account balances, transactions, and statements. Please ask me about your banking needs.",
            "iterations": 0
        }
    
    # SECOND: Check if user is asking about a different account
    is_valid, error_msg = check_account_access(user_question, user_account_id, masked_account)
    if not is_valid:
        return {
            "type": "error",
            "response": error_msg,
            "iterations": 0
        }
    
    conversation_history = []
    iteration = 0
    
    # Add initial user question
    conversation_history.append({
        "role": "user",
        "content": user_question
    })
    
    print(f"\n{'='*60}")
    print(f"🤖 AGENT STARTED")
    print(f"User: {username} (Account: {masked_account})")
    print(f"Question: {user_question}")
    print(f"{'='*60}\n")
    
    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")
        
        # Build context with MASKED account ID for LLM
        context = f"[User: {username}, AccountID: {masked_account}]\n"
        context += f"Original Question: {user_question}\n\n"
        
        if len(conversation_history) > 1:
            context += "Previous steps:\n"
            for i, msg in enumerate(conversation_history[1:], 1):
                content_preview = str(msg['content'])[:100]
                # Mask any account IDs in the preview
                content_preview = content_preview.replace(str(user_account_id), masked_account)
                context += f"{i}. {msg['role']}: {content_preview}...\n"
        
        # Decide next action
        decision_prompt = f"""
{context}

Based on the conversation so far, decide what to do next:

OPTIONS:
1. Call a tool (get_account_balance, get_transaction_history, get_periodic_statements, get_adhoc_statements)
2. Provide a final answer to the user
3. Ask for clarification

Think step by step:
- Have I gathered all the information needed to answer the question?
- Do I need to call any more tools?
- Can I provide a complete answer now?

Respond in JSON format:
{{
  "reasoning": "explain your thinking",
  "action": "tool" or "answer" or "clarify",
  "tool_name": "tool name if action is tool",
  "tool_args": {{}},
  "response": "your answer or clarification question"
}}

NOTE: You don't need to specify account_id in tool_args - it will be automatically provided.
"""
        
        print(f"🤔 Agent is thinking...")
        decision_response = llm.invoke(decision_prompt)
        print(f"💭 Decision: {decision_response[:200]}...")
        
        # Parse decision
        try:
            # Clean JSON response
            decision_response = decision_response.strip()
            if decision_response.startswith("```json"):
                decision_response = decision_response.split("```json")[1].split("```")[0].strip()
            elif decision_response.startswith("```"):
                decision_response = decision_response.split("```")[1].split("```")[0].strip()
            
            decision = json.loads(decision_response)
            
            print(f"📋 Action: {decision.get('action')}")
            print(f"🧠 Reasoning: {decision.get('reasoning', 'N/A')[:100]}")
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse decision: {e}")
            # Fallback: try to answer directly
            return {
                "type": "answer",
                "response": decision_response,
                "iterations": iteration
            }
        
        # Execute action
        action = decision.get("action", "answer")
        
        if action == "tool":
            # Execute tool
            tool_name = decision.get("tool_name")
            tool_args = decision.get("tool_args", {})
            
            # IMPORTANT: Always ensure account_id matches the logged-in user
            # Override any account_id in the decision with the user's actual account
            tool_args["account_id"] = user_account_id
            
            print(f"🔧 Calling tool: {tool_name} with args: {tool_args}")
            
            try:
                tool_result = execute_tool(tool_name, tool_args)
                print(f"✅ Tool result received: {str(tool_result)[:100]}...")
                
                # MASK the account ID in tool result before storing
                masked_tool_result = mask_account_in_data(tool_result, user_account_id)
                
                # Add MASKED result to conversation history
                conversation_history.append({
                    "role": "tool",
                    "tool": tool_name,
                    "content": json.dumps(masked_tool_result, indent=2)
                })
                
            except Exception as e:
                print(f"❌ Tool execution failed: {e}")
                conversation_history.append({
                    "role": "error",
                    "content": f"Tool {tool_name} failed: {str(e)}"
                })
        
        elif action == "answer":
            # Provide final answer
            print(f"✅ Agent providing final answer")
            
            # Generate final answer using all gathered information (already masked)
            final_prompt = f"""
You are a banking assistant. Answer the user's question based on the information gathered.

User Question: {user_question}

Information gathered:
{json.dumps(conversation_history, indent=2)}

Provide a clear, professional answer. Use specific numbers, dates, and details from the data.
Format currency properly (e.g., $1,234.56).
When referring to the account, use the masked format shown in the data.
"""
            
            final_answer = llm.invoke(final_prompt)
            
            return {
                "type": "answer",
                "response": final_answer,
                "iterations": iteration,
                "tools_used": [msg for msg in conversation_history if msg.get("role") == "tool"]
            }
        
        elif action == "clarify":
            # Need clarification
            return {
                "type": "clarify",
                "response": decision.get("response", "Could you please provide more information?"),
                "iterations": iteration
            }
        
        else:
            # Unknown action, default to answering
            return {
                "type": "answer",
                "response": decision.get("response", "I'm not sure how to help with that."),
                "iterations": iteration
            }
    
    # Max iterations reached
    print(f"⚠️ Max iterations ({max_iterations}) reached")
    
    # Try to provide best answer with available information
    final_prompt = f"""
Based on the information gathered so far, provide the best answer you can to: {user_question}

Information available:
{json.dumps(conversation_history, indent=2)}
"""
    
    final_answer = llm.invoke(final_prompt)
    
    return {
        "type": "partial_answer",
        "response": final_answer,
        "iterations": iteration,
        "note": "Maximum iterations reached. This may be a partial answer."
    }


def run_simple_agent(user_question: str, user_account_id: int, username: str):
    """
    Simplified agentic approach - tries to decompose complex questions
    """
    
    # First, analyze if question needs multiple steps
    analysis_prompt = f"""
Analyze this banking question: "{user_question}"

Does this require multiple pieces of information or calculations?

Examples of multi-step questions:
- "What's my total spending on groceries last month?" (needs transactions + filtering)
- "Compare my balance from last month to now" (needs balance history)
- "How much did I save in Q1?" (needs periodic statements + calculation)

Respond in JSON:
{{
  "is_complex": true/false,
  "steps": ["step 1", "step 2", ...],
  "tools_needed": ["tool1", "tool2", ...]
}}
"""
    
    analysis = llm.invoke(analysis_prompt)
    print(f"📊 Question Analysis: {analysis}")
    
    # Run the full agentic loop
    return run_agent(user_question, user_account_id, username)