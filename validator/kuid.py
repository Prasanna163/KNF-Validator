from __future__ import annotations

from .schema import KUID_INT_BOUNDS, KUID_INT_FEATURES


def encode_linear(value: float, lo: float, hi: float, bins: int) -> int:
    if hi <= lo:
        return 0
    frac = (value - lo) / (hi - lo)
    frac = max(0.0, min(1.0, frac))
    return min(int(frac * bins), bins - 1)


def assign_kuid_int_from_values(values: dict[str, float]) -> str:
    digits: list[str] = []
    for feature in KUID_INT_FEATURES:
        lo, hi, scale, bins = KUID_INT_BOUNDS[feature]
        value = float(values[feature])
        if scale == "linear":
            bin_index = encode_linear(value, lo, hi, bins)
        else:
            bin_index = encode_linear(value, lo, hi, bins)
        digits.append(format(bin_index, "X"))
    return "-".join(digits)


def assign_kuid_int_rows(rows: list[dict[str, object]]) -> None:
    for row in rows:
        if row.get("_decision_class"):
            continue
        numeric = row.get("_num", {})
        if not isinstance(numeric, dict):
            continue
        try:
            values = {feature: float(numeric[feature]) for feature in KUID_INT_FEATURES}
        except (KeyError, TypeError, ValueError):
            continue
        row["_kuid_int"] = assign_kuid_int_from_values(values)
