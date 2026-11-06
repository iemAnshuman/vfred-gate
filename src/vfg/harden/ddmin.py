"""Delta debugging over a finite set of hardening sites."""


def _split(items, parts):
    size = len(items)
    return [items[i * size // parts : (i + 1) * size // parts] for i in range(parts)]


def ddmin(items, test, max_tests=200):
    """Return a 1-minimal subset for which ``test`` passes.

    ``test`` receives a list of items and returns True when the contract passes.
    Every call is recorded so the search is auditable.
    """
    items = list(items)
    trace = []

    def check(subset):
        if len(trace) >= max_tests:
            raise RuntimeError("ddmin test budget exhausted")
        passed = bool(test(list(subset)))
        trace.append({"subset": list(subset), "size": len(subset), "passed": passed})
        return passed

    if not items:
        return [], trace
    if not check(items):
        raise RuntimeError("the full hardening set does not restore the contract")
    current = items
    parts = 2
    while len(current) >= 2:
        chunks = _split(current, parts)
        reduced = False
        for chunk in chunks:
            complement = [item for item in current if item not in chunk]
            if complement and check(complement):
                current = complement
                parts = max(parts - 1, 2)
                reduced = True
                break
        if not reduced:
            if parts >= len(current):
                break
            parts = min(len(current), parts * 2)
    # Explicit 1-minimality: removing any remaining site must fail.
    for item in list(current):
        complement = [other for other in current if other != item]
        if complement and check(complement):
            current = complement
            break
    return current, trace
