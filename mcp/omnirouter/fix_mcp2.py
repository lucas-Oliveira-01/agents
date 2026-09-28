with open("gateway/omniroute_mcp.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'return f"[tool error] UNHANDLED: {str(e)}' in line:
        pass # Drop it
    elif '{traceback.format_exc()}"' in line:
        new_lines.append('            return f"[tool error] UNHANDLED: {str(e)}\\n{traceback.format_exc()}"\n')
    else:
        new_lines.append(line)

with open("gateway/omniroute_mcp.py", "w") as f:
    f.writelines(new_lines)
