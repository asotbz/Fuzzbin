import json

from fuzzbin.web.main import create_app
app = create_app()
with open("docs/openapi.json", "w") as f:
    json.dump(app.openapi(), f, indent=2)
print("wrote docs/openapi.json")

spec = json.load(open("docs/openapi.json"))
md = ["# Fuzzbin API UI Spec\n"]
for tag in spec.get("tags", []):
    md.append(f"## {tag['name']}\n{tag.get('description','')}\n")
    for path, methods in spec.get("paths", {}).items():
        for verb, op in methods.items():
            if tag["name"] not in op.get("tags", []):
                continue
            summary = op.get("summary","")
            desc = op.get("description","")
            md.append(f"- `{verb.upper()}` `{path}` — {summary}")
            if desc:
                md.append(f"  - {desc}")
    md.append("")
open("docs/openapi-spec.md","w").write("\n".join(md))
print("wrote openapi-spec.md")
