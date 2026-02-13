from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

LSB_BUS_LETTER_MAP: Dict[str, int] = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
}


def normalize_lsb_key(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    match = re.search(r"LSB\s*([0-9]+)\s*[-_/ ]\s*([0-9]+)", text, re.IGNORECASE)
    if match:
        return f"LSB{int(match.group(1))}-{int(match.group(2))}"

    match = re.search(r"LSB\s*_?\s*([0-9]+)\s*_+\s*([0-9]+)", text, re.IGNORECASE)
    if match:
        return f"LSB{int(match.group(1))}-{int(match.group(2))}"

    match = re.search(r"LSB\s*([A-H])\s*(?:Teilnehmer\s*)?Adr\.?\s*([0-9]+)", text, re.IGNORECASE)
    if match:
        bus = LSB_BUS_LETTER_MAP.get(match.group(1).upper())
        if bus:
            return f"LSB{bus}-{int(match.group(2))}"

    match = re.match(r"^\s*([0-9]+)\s*[- ]\s*([0-9]+)\s*$", text)
    if match:
        return f"LSB{int(match.group(1))}-{int(match.group(2))}"

    match = re.search(r"Adr\.?\s*([0-9]+)\s*([0-9]+)\s*[-–]\s*([0-9]+)", text, re.IGNORECASE)
    if match:
        return f"LSB{int(match.group(2))}-{int(match.group(3))}"

    return None


def full_lsb_address(err: Dict[str, Any]) -> Optional[str]:
    raw = err.get("raw_block") or ""
    if not raw:
        return None
    first_line = str(raw).splitlines()[0].strip()
    if not first_line:
        return None
    return first_line


def lsb_keys_from_bmk_lsb(raw: Any) -> List[str]:
    if raw is None:
        return []

    text = str(raw).strip()
    if not text:
        return []

    match = re.match(r"^\s*([0-9]+)\s+([0-9]+)\s*[-–]\s*([0-9]+)\s*$", text)
    if match:
        bus = int(match.group(1))
        address_1 = int(match.group(2))
        address_2 = int(match.group(3))
        if address_2 < address_1:
            address_1, address_2 = address_2, address_1
        return [f"LSB{bus}-{address}" for address in range(address_1, address_2 + 1)]

    match = re.match(r"^\s*([0-9]+)\s*[-–]\s*([0-9]+)\s+([0-9]+)\s*$", text)
    if match:
        bus_1 = int(match.group(1))
        bus_2 = int(match.group(2))
        address = int(match.group(3))
        if bus_2 < bus_1:
            bus_1, bus_2 = bus_2, bus_1
        return [f"LSB{bus}-{address}" for bus in range(bus_1, bus_2 + 1)]

    key = normalize_lsb_key(text)
    return [key] if key else []


def extract_lsb_key_from_error_data(err: Dict[str, Any]) -> Optional[str]:
    raw = err.get("lsb_address") or err.get("lsb")
    key = normalize_lsb_key(raw)
    if key:
        return key
    text = (err.get("long_text") or "") + "\n" + (err.get("short_text") or "")
    return normalize_lsb_key(text)


def looks_like_lsb_query(query: str) -> Optional[str]:
    query = (query or "").strip()
    if not query:
        return None
    return normalize_lsb_key(query)
