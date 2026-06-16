from dataclasses import dataclass


@dataclass(frozen=True)
class QualityGateDecision:
    eligible: bool
    status: str
    apply_new_plan: bool = True


def evaluate_quality_gate(
    metrics: dict[str, float],
    *,
    metric: str,
    value: float,
    index_version: str,
    current_version: str,
    allow_unverified: bool = False,
) -> QualityGateDecision:
    if index_version != current_version:
        return QualityGateDecision(eligible=False, status="needs_recalibration", apply_new_plan=False)
    if metric not in metrics:
        return QualityGateDecision(eligible=allow_unverified, status="unverifiable")
    if metrics[metric] < value:
        return QualityGateDecision(eligible=False, status="below_gate")
    return QualityGateDecision(eligible=True, status="passed")
