with open("src/project_audit/semantic_auditor.py", "r") as f:
    content = f.read()

# Replace:
#         except SemanticOutputError:
# with:
#         except SemanticOutputError as e:
#             print(f"DEBUG SCHEMA VIOLATION: {e}")

content = content.replace("        except SemanticOutputError:", '        except SemanticOutputError as e:\n            print(f"DEBUG SCHEMA VIOLATION: {e}")')

with open("src/project_audit/semantic_auditor.py", "w") as f:
    f.write(content)
