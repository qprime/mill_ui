
import json, pathlib
def save_json(path, obj): p=pathlib.Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding='utf-8'); return str(p.resolve())
def load_json(path): return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
