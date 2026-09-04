"""Stable, independently keyed streams with sample-size prefix invariance."""
import hashlib
import numpy as np


def rng_for(seed: int, key: str):
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    words = [int.from_bytes(digest[i:i+4], "little") for i in range(0, 16, 4)]
    return np.random.default_rng(np.random.SeedSequence([int(seed), *words]))
