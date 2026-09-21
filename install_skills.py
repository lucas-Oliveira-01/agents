import json
import os

with open("/home/oliveira/.gemini/antigravity-cli/brain/cf5de5d9-07ec-4649-8306-680296556822/.system_generated/steps/535/output.txt") as f:
    data = json.load(f)

for skill in data["managed_skills"]:
    path = os.path.expanduser(os.path.join("~/.agents/skills", skill["relative_path"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as out:
        out.write(skill["content"])
    print(f"Installed {path}")
