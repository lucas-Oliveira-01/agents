with open("src/project_audit/omniroute_backend.py", "r") as f:
    content = f.read()

import re

# We will use regex to replace the whole block from "if isinstance(content, list):" to "return payload"
old_pattern = r"if isinstance\(content, list\):.*?text_result = text_result\.split\(\"```\"\).*?return payload"
new_code = """nested = result.get("structuredContent")
        if isinstance(nested, dict) and nested:
            return nested

        if isinstance(content, list):
            text_blocks = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            text_result = "".join(text_blocks).strip()
            
            if text_result:
                # Find first { and last }
                start_idx = text_result.find("{")
                end_idx = text_result.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = text_result[start_idx:end_idx+1]
                    try:
                        import json
                        payload = json.loads(json_str)
                        if not isinstance(payload, dict):
                            raise ValueError("OmniRoute semantic payload must be an object.")
                        return payload
                    except json.JSONDecodeError as exc:
                        raise ValueError("OmniRoute returned non-JSON semantic output.") from exc
                else:
                    raise ValueError("No JSON object could be extracted from OmniRoute text response.")
                    
        raise ValueError("OmniRoute MCP result contains no structured semantic payload.")"""

# Actually it's safer to just replace everything from "if isinstance(content, list):" down to "raise ValueError("OmniRoute MCP result contains no structured semantic payload.")"
start_str = "if isinstance(content, list):"
end_str = "raise ValueError(\"OmniRoute MCP result contains no structured semantic payload.\")"

start_idx = content.find(start_str)
end_idx = content.find(end_str) + len(end_str)

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_code + content[end_idx:]

with open("src/project_audit/omniroute_backend.py", "w") as f:
    f.write(content)
