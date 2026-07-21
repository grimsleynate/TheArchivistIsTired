# equipment_slots.py
MAIN_HAND = "main_hand"
OFF_HAND = "off_hand"
HEAD = "head"
BODY = "body"
BACK = "back"
NECK = "neck"
RING_ONE = "finger"
RING_TWO = "finger"
FEET = "feet"
HANDS = "hands"  # gloves
# Add more as needed

# Legacy mapping
LEGACY_SLOT_MAP = {
    "hand": [MAIN_HAND],   # treat "hand" as main_hand by default
    "twohand": [MAIN_HAND, OFF_HAND],
    "both_hands": [MAIN_HAND, OFF_HAND],
}

def normalize_slot_entry(entry):
    """
    Accepts either a string slot, a list of strings, or legacy names.
    Returns a list of canonical slot names.
    """
    if entry is None:
        return []
    if isinstance(entry, str):
        # legacy mapping
        if entry in LEGACY_SLOT_MAP:
            return LEGACY_SLOT_MAP[entry]
        return [entry]
    if isinstance(entry, (list, tuple)):
        out = []
        for e in entry:
            out.extend(normalize_slot_entry(e))
        return out
    return []
