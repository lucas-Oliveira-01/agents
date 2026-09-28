with open("gateway/omniroute_mcp.py", "r") as f:
    content = f.read()
import re
content = re.sub(r'return f"\[tool error\] UNHANDLED: \{str\(e\)\}\n\{traceback\.format_exc\(\)\}"', 'return f"[tool error] UNHANDLED: {str(e)}\\n{traceback.format_exc()}"', content)
with open("gateway/omniroute_mcp.py", "w") as f:
    f.write(content)
