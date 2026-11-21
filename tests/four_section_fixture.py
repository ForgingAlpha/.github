"""Lane-neutral bytes and expected hashes for the four-section contract."""
import hashlib
import json
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures/four-section"
CASES = json.loads((FIXTURE / "cases.json").read_text())
README = (FIXTURE / "readme.txt").read_bytes()
TRIO = ["README.md#" + kind for kind in ("intent", "requirements", "architecture")]
LOCAL = "README.md#local-instructions"
KEY = "readme_four_section_scopes"
MANIFEST = "docs/governing-source-bindings.json"
DETAIL = {"requirements": "docs/observations.md", "architecture": "docs/storage.md"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest(selection, meta):
    hashes = CASES["digests"]
    sources = []
    for index, path in enumerate(TRIO):
        upstream = []
        for parent in TRIO[:index]:
            kind = parent.split("#")[1]
            edge = {"path": parent, "sha256": hashes[kind]}
            if kind in DETAIL:
                edge["detail_sha256"] = CASES["details"][DETAIL[kind]]
            upstream.append(edge)
        kind = path.split("#")[1]
        sources.append({"id": "urn:example:" + kind, "path": path, "sha256": hashes[kind], "upstream": upstream})
    for kind, path in DETAIL.items():
        sources.append({"id": path, "path": path, "sha256": CASES["details"][path],
                        "upstream": [{"path": "README.md#" + kind, "sha256": hashes[kind]}]})
    return {"schema_version": 3, KEY: selection, "sources": sources, "source_metadata": meta,
            "local_instructions": {"path": LOCAL, "sha256": hashes["local-instructions"]}}


def documents(branch="main"):
    selection = {branch: ["."]}
    ids = {kind: "urn:example:" + kind for kind in ("intent", "requirements", "architecture")}
    meta = {TRIO[1]: {"id": ids["requirements"], "intent": ids["intent"], "status": "approved",
                      "readme_intent_scopes": selection, KEY: selection},
            TRIO[2]: {"id": ids["architecture"], "intent": ids["intent"], "requirements": ids["requirements"],
                      "status": "approved"}}
    return meta, manifest(selection, meta)


def details():
    return {path: (FIXTURE / (Path(path).stem + ".txt")).read_bytes() for path in DETAIL.values()}
