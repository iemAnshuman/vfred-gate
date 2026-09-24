import numpy as np


def top_two_margins(logits):
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] < 2 or not np.isfinite(values).all():
        raise ValueError("finite logit matrix with at least two entries required")
    pairs = np.partition(values, -2, axis=1)[:, -2:]
    return pairs.max(axis=1) - pairs.min(axis=1)
