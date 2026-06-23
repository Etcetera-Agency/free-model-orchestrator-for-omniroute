from dataclasses import dataclass


@dataclass(frozen=True)
class AttributionGroup:
    group_id: str
    status: str
    limit: float
    recalculate_allocation: bool = False


@dataclass(frozen=True)
class Capacity:
    guaranteed: float
    opportunistic: float


def attribution_capacity(groups: list[AttributionGroup]) -> Capacity:
    guaranteed = 0.0
    opportunistic = 0.0
    assumed_shared_counted = False
    for group in groups:
        if group.status == "confirmed":
            guaranteed += group.limit
        elif group.status == "inferred":
            opportunistic += group.limit * 0.5
        elif group.status == "assumed_shared" and not assumed_shared_counted:
            guaranteed += group.limit
            assumed_shared_counted = True
    return Capacity(guaranteed=guaranteed, opportunistic=opportunistic)


def apply_group_evidence(groups: list[AttributionGroup], *, evidence: dict) -> list[AttributionGroup]:
    if evidence.get("shared_counter"):
        return [
            AttributionGroup(
                group_id="+".join(group.group_id for group in groups),
                status="confirmed",
                limit=max(group.limit for group in groups),
                recalculate_allocation=True,
            )
        ]
    if evidence.get("confirmed_independence"):
        return [
            AttributionGroup(
                group_id=group.group_id, status="confirmed", limit=group.limit, recalculate_allocation=True
            )
            for group in groups
        ]
    return groups
