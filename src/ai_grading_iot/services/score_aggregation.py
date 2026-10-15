from decimal import Decimal, ROUND_HALF_UP


def aggregate_scores(weights: dict[str, float], scores: dict[str, float | None]) -> float | None:
    if set(weights) != {"code", "data", "vision"}:
        raise ValueError("Exactly three rubric weights are required")
    values = {key: Decimal(str(value)) for key, value in weights.items()}
    if any(value < 0 or value > 100 for value in values.values()) or sum(values.values()) != 100:
        raise ValueError("Rubric weights must total 100")
    total = Decimal(0)
    for key, weight in values.items():
        score = scores.get(key)
        if weight > 0 and score is None:
            return None
        if score is not None:
            amount = Decimal(str(score))
            if not amount.is_finite() or not 0 <= amount <= 100:
                raise ValueError("Invalid score")
            total += amount * weight
    return float((total / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
