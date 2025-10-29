from __future__ import annotations
from datetime import datetime
from typing import Any

def _op_eq(v, arg): return v == arg
def _op_neq(v, arg): return v != arg
def _op_in(v, arg): return v in arg if isinstance(arg, (list, set, tuple)) else False
def _op_contains(v, arg): return (arg in v) if isinstance(v, str) else False

def _op_contains_any(v, arg):
    # v is a string; arg is a list of substrings
    if not isinstance(v, str) or not isinstance(arg, (list, tuple, set)):
        return False
    return any(sub in v for sub in arg)

def _op_any(v, arg):  # any overlap for lists
    if not isinstance(v, list) or not isinstance(arg, (list, set, tuple)):
        return False
    s = set(v); return any(x in s for x in arg)

def _to_dt(x):
    if isinstance(x, datetime): return x
    return datetime.fromisoformat(x)

def _op_ge(v, arg): return v >= arg
def _op_le(v, arg): return v <= arg
def _op_gt(v, arg): return v > arg
def _op_lt(v, arg): return v < arg

_OPS = {
    "eq": _op_eq, "neq": _op_neq, "in": _op_in, "contains": _op_contains, "any": _op_any,
    ">=": _op_ge, "<=": _op_le, ">": _op_gt, "<": _op_lt, "contains_any": _op_contains_any
}

def _get_field(obj: Any, path: str):
    # supports dotted paths like "metadata.created_at" or "metadata.tags"
    cur = obj
    for part in path.split("."):
        cur = getattr(cur, part) if hasattr(cur, part) else (cur.get(part) if isinstance(cur, dict) else None)
        if cur is None: break
    return cur

def _coerce_for_cmp(field_path: str, value):
    # Treat *created_at* fields as datetime if value parses
    if field_path.endswith("created_at") and isinstance(value, (str, datetime)):
        try: return _to_dt(value)
        except Exception: return value
    return value

def match_obj(obj: Any, spec: dict[str, Any]) -> bool:
    """
    spec format: { "field_name": { "op": arg, ... }, ... }
    example: { "metadata.tags": {"any": ["ml","ai"]}, "metadata.name": {"contains": "foo"} }
    """
    if not spec: return True
    for field, ops in spec.items():
        v = _get_field(obj, field)
        ok = True
        for op, arg in ops.items():
            fn = _OPS.get(op)
            if not fn: continue
            vv = _coerce_for_cmp(field, v)
            aa = _coerce_for_cmp(field, arg)
            if not fn(vv, aa):
                ok = False
                break
        if not ok:
            return False
    return True
