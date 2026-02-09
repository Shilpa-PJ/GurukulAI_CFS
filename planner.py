import json
from langchain_ollama import OllamaLLM
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
import re

llm = OllamaLLM(
    model="gemma3:4b",
    base_url="http://localhost:11434"
)

TOOLS = {
    "get_account_balance": ["account_id"],
    "get_transaction_history": ["account_id"],
    "get_adhoc_statements": ["account_id"],
    "get_periodic_statements": ["account_id"],
}

# Initialize chat history storage (supports multiple sessions)
chat_histories = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """
    Get or create chat history for a session.
    Maintains last 10 messages per session.
    """
    if session_id not in chat_histories:
        chat_histories[session_id] = InMemoryChatMessageHistory()
    
    # Trim to last 10 messages (5 exchanges)
    history = chat_histories[session_id]
    if len(history.messages) > 10:
        history.messages = history.messages[-10:]
    
    return chat_histories[session_id]


def extract_json(text: str) -> str:
    """Extract JSON from LLM response"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
    return text


def create_banking_chain():
    """Create a chain with message history support"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a banking assistant.

Decide what to do with the user's message based on conversation history.

Rules:
- If the question requires bank data, return a TOOL call
- If it is casual or informational, return CHAT
- If it is unrelated to banking (food, sports, politics), return REJECT
- Use conversation history to understand context and provide relevant responses

Available tools:
- get_account_balance(account_id)
- get_transaction_history(account_id)
- get_adhoc_statements(account_id)
- get_periodic_statements(account_id)

Return ONLY valid JSON in one of these formats.

TOOL:
{{ "type": "tool", "tool": "...", "args": {{...}} }}

CHAT:
{{ "type": "chat", "response": "..." }}

REJECT:
{{ "type": "reject", "response": "..." }}"""),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
    
    chain = prompt | llm
    
    # Wrap chain with message history
    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )
    
    return chain_with_history


# Create the chain with history
banking_chain = create_banking_chain()


def plan_tool_call(user_message: str, session_id: str = "default") -> dict:
    """
    Plan tool call with conversation history
    
    Args:
        user_message: The user's input message
        session_id: Session identifier for maintaining separate conversation histories
    
    Returns:
        Response dictionary with type, tool/response, and metadata
    """
    
    # Check if this exact question was asked recently in history
    history = get_session_history(session_id)
    for i in range(len(history.messages) - 2, -1, -2):  # Check previous user messages
        if i >= 0 and isinstance(history.messages[i], HumanMessage):
            if history.messages[i].content.strip().lower() == user_message.strip().lower():
                # Return cached response
                if i + 1 < len(history.messages) and isinstance(history.messages[i + 1], AIMessage):
                    cached_content = history.messages[i + 1].content
                    try:
                        cached_response = json.loads(extract_json(cached_content))
                        cached_response["cached"] = True
                        print("✓ CACHE HIT - Using response from history")
                        return cached_response
                    except:
                        pass
    
    # Invoke chain with history
    response = banking_chain.invoke(
        {"input": user_message},
        config={"configurable": {"session_id": session_id}}
    ).strip()
    
    print("RAW LLM RESPONSE:")
    print(repr(response))
    
    if not response or not response.strip():
        raise ValueError("LLM returned empty response")
    
    cleaned = extract_json(response)
    result = json.loads(cleaned)
    result["cached"] = False
    
    return result


def get_conversation_summary(session_id: str = "default") -> dict:
    """Get summary of conversation history"""
    history = get_session_history(session_id)
    
    user_messages = []
    ai_messages = []
    
    for msg in history.messages:
        if isinstance(msg, HumanMessage):
            user_messages.append(msg.content)
        elif isinstance(msg, AIMessage):
            ai_messages.append(msg.content)
    
    return {
        "session_id": session_id,
        "total_messages": len(history.messages),
        "user_messages_count": len(user_messages),
        "ai_messages_count": len(ai_messages),
        "recent_user_messages": user_messages[-3:],
    }


def clear_history(session_id: str = "default"):
    """Clear conversation history for a session"""
    if session_id in chat_histories:
        chat_histories[session_id].clear()
        print(f"✓ Cleared history for session: {session_id}")


def list_sessions() -> list:
    """List all active session IDs"""
    return list(chat_histories.keys())


# Example usage and testing
if __name__ == "__main__":
    print("=== Banking Assistant with LangChain Memory ===\n")
    
    # Test queries with session
    test_queries = [
        "What's my account balance?",
        "Show me transaction history",
        "What's my account balance?",  # Duplicate - should use cache
        "Can you help me with my periodic statements?",
        "Tell me about your services",
        "What's the weather like?",
    ]
    
    session_id = "user_123"
    
    for query in test_queries:
        print(f"\n📩 User: {query}")
        try:
            response = plan_tool_call(query, session_id=session_id)
            print(f"🤖 Response: {json.dumps(response, indent=2)}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Show conversation summary
    print("\n" + "="*50)
    print("Conversation Summary:")
    print(json.dumps(get_conversation_summary(session_id), indent=2))
    
    # Show message history
    print("\n" + "="*50)
    print("Message History:")
    history = get_session_history(session_id)
    for i, msg in enumerate(history.messages, 1):
        msg_type = "User" if isinstance(msg, HumanMessage) else "Assistant"
        content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        print(f"{i}. [{msg_type}]: {content}")
    
    # Test with different session
    print("\n" + "="*50)
    print("\nTesting with different session:")
    response = plan_tool_call("Show balance", session_id="user_456")
    print(f"🤖 Response: {json.dumps(response, indent=2)}")
    
    print(f"\nActive sessions: {list_sessions()}")
    
    # Clear specific session
    clear_history(session_id)
