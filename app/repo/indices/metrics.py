import math

def dot(a: list[float], b: list[float]) -> float:
    return sum(x*y for x,y in zip(a,b))

def l2sq(a: list[float], b: list[float]) -> float:
    return sum((x-y)*(x-y) for x,y in zip(a,b))

def cosine(a: list[float], b: list[float]) -> float:
    # assumes already normalized; fall back to dot / (||a|| ||b||) if needed
    return dot(a, b)
