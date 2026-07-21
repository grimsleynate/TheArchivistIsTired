from typing import List, Optional

def compose_starting_equipment(race, subrace: Optional[object], cls: Optional[object]) -> List[str]:
    """
    Additive composition: race.starting_equipment + subrace.starting_equipment + class.starting_equipment
    Deduplicate preserving first occurrence order.
    """
    result = []

    if getattr(race, "starting_equipment", None):
        result.extend(race.starting_equipment)

    if subrace and getattr(subrace, "starting_equipment", None):
        result.extend(subrace.starting_equipment)

    if cls and getattr(cls, "starting_equipment", None):
        result.extend(cls.starting_equipment)

    seen = set()
    final = []
    for item_id in result:
        if item_id not in seen:
            seen.add(item_id)
            final.append(item_id)

    return final
