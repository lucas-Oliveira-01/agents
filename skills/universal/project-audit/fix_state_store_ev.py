with open("src/project_audit/state_store.py", "r") as f:
    content = f.read()

content = content.replace('"evidences": self.root / "evidences"', '"evidence": self.root / "evidence"')
# Ensure save_evidence uses "evidence"
content = content.replace('self._dirs["evidences"]', 'self._dirs["evidence"]')
# Just to be safe, any remaining 'evidences' dict key should be fixed
with open("src/project_audit/state_store.py", "w") as f:
    f.write(content)
