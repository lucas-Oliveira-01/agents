with open("src/project_audit/runtime.py", "r") as f:
    content = f.read()

old_norm = """        normalized_dir = resolved_output_dir / "normalized"
        if normalize:"""

new_norm = """        normalized_dir = resolved_output_dir / "normalized"
        if normalized_dir.exists() and normalized_dir.is_symlink():
            if not normalized_dir.resolve().is_relative_to(resolved_output_dir.resolve()):
                raise ValueError(f"Security violation: normalized directory {normalized_dir} escapes audit vault.")

        if normalize:"""

if old_norm in content:
    content = content.replace(old_norm, new_norm)

with open("src/project_audit/runtime.py", "w") as f:
    f.write(content)
