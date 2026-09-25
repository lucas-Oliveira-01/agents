with open("src/project_audit/__main__.py", "r") as f:
    content = f.read()

# Add --allow-external
old_str = 'parser.add_argument("--auto-fix-p1", action="store_true", help="Auto-dispatch OpenCode workers for P1 findings")'
new_str = 'parser.add_argument("--auto-fix-p1", action="store_true", help="Auto-dispatch OpenCode workers for P1 findings")\n    parser.add_argument("--allow-external", action="store_true", help="Explicitly allow external egress")'
content = content.replace(old_str, new_str)

with open("src/project_audit/__main__.py", "w") as f:
    f.write(content)
