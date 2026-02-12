"""
weighted_sampler.py

Reusable weighted sampling utilities.
All generators MUST use this module instead of ad-hoc random selection logic.

Design goals:
- deterministic when seeded (support injecting a random.Random instance)
- validates weight maps (non-negative, non-empty, sum > 0)
- keeps behaviour consistent across the project
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Generic, Iterable, List, Optional, Sequence, Tuple, TypeVar
import random

T = TypeVar("T")


class WeightError(ValueError):
    pass


def _validate_weights(weight_map: Dict[T, float]) -> None:
    if not weight_map:
        raise WeightError("Weight map is empty.")

    total = 0.0
    for k, w in weight_map.items():
        if w is None:
            raise WeightError(f"Weight is None for key={k!r}.")
        if w < 0:
            raise WeightError(f"Negative weight {w} for key={k!r}.")
        total += float(w)

    if total <= 0.0:
        raise WeightError("Sum of weights must be > 0.")


def normalised(weight_map: Dict[T, float]) -> Dict[T, float]:
    """
    Returns a new dict with weights normalised to sum to 1.0.
    """
    _validate_weights(weight_map)
    total = float(sum(float(w) for w in weight_map.values()))
    return {k: float(w) / total for k, w in weight_map.items()}


def weighted_choice(weight_map: Dict[T, float], rng: Optional[random.Random] = None) -> T:
    """
    Weighted random choice from a dict {item: weight}.
    """
    _validate_weights(weight_map)
    r = rng or random

    items: List[T] = list(weight_map.keys())
    weights: List[float] = [float(weight_map[i]) for i in items]

    # random.choices exists on both random.Random and module random
    return r.choices(items, weights=weights, k=1)[0]


def bernoulli(p: float, rng: Optional[random.Random] = None) -> bool:
    """
    Returns True with probability p.
    """
    if p < 0.0 or p > 1.0:
        raise ValueError(f"Probability must be in [0,1], got {p}.")
    r = rng or random
    return r.random() < p


@dataclass(frozen=True)
class WeightedPolicy(Generic[T]):
    """
    Convenience wrapper to hold a weight map plus optional name for debugging.
    """
    weights: Dict[T, float]
    name: str = "UnnamedPolicy"

    def choose(self, rng: Optional[random.Random] = None) -> T:
        return weighted_choice(self.weights, rng=rng)

    def normalised(self) -> Dict[T, float]:
        return normalised(self.weights)
