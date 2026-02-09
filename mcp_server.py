from fastmcp import FastMCP
import requests

BASE_API_URL = "http://localhost:8000"

mcp = FastMCP("banking-mcp-tools")

# Store the raw functions, not the decorated ones
TOOLS = {}   


def get_account_balance_fn(account_id: int) -> dict:
    """Get account balance"""
    r = requests.get(f"{BASE_API_URL}/api/accounts/{account_id}/balance")
    r.raise_for_status()
    return r.json()


def get_transaction_history_fn(account_id: int) -> dict:
    """Get transaction history"""
    r = requests.get(f"{BASE_API_URL}/api/accounts/{account_id}/transactions")
    r.raise_for_status()
    return r.json()


def get_adhoc_statements_fn(account_id: int) -> dict:
    """Get ad-hoc statements"""
    r = requests.get(
        f"{BASE_API_URL}/api/accounts/{account_id}/statements/adhoc"
    )
    r.raise_for_status()
    return r.json()


def get_periodic_statements_fn(account_id: int) -> dict:
    """Get periodic statements"""
    r = requests.get(
        f"{BASE_API_URL}/api/accounts/{account_id}/statements/current"
    )
    r.raise_for_status()
    return r.json()


# Store raw functions in TOOLS dictionary
TOOLS["get_account_balance"] = get_account_balance_fn
TOOLS["get_transaction_history"] = get_transaction_history_fn
TOOLS["get_adhoc_statements"] = get_adhoc_statements_fn
TOOLS["get_periodic_statements"] = get_periodic_statements_fn

# Register with MCP (for MCP functionality)
mcp.tool()(get_account_balance_fn)
mcp.tool()(get_transaction_history_fn)
mcp.tool()(get_adhoc_statements_fn)
mcp.tool()(get_periodic_statements_fn)