from mcp_server import TOOLS


def execute_tool(tool_name: str, args: dict):
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool = TOOLS[tool_name]

    # Normalize parameter names to match what the tool functions expect
    normalized_args = {}
    
    for key, value in args.items():
        # Convert various accountId formats to 'account_id' (what mcp_server expects)
        if key in ["accountId", "account_id", "account", "account_number"]:
            normalized_args["account_id"] = int(value)
        else:
            normalized_args[key] = value
    
    print(f"Executing tool: {tool_name}")
    print(f"Original args: {args}")
    print(f"Normalized args: {normalized_args}")
    
    # Call the function directly (not the FunctionTool wrapper)
    # The tool IS the function since we stored it directly in mcp_server.py
    return tool(**normalized_args)