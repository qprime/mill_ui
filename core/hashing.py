
import json, hashlib
def dump_canonical(obj)->str: return json.dumps(obj, indent=2, sort_keys=True, separators=(',',':'))
def stable_hash(obj)->str: return hashlib.sha256(dump_canonical(obj).encode('utf-8')).hexdigest()[:16]
