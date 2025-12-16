# scripts/lsb_utils.py

from __future__ import annotations
import re
from typing import Optional, Union

LSB_LETTER_TO_NUMBER = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
}


def _extract_int(value: Union[str, int, None]) -> Optional[int]:
    """Hilfsfunktion: erste Ganzzahl aus String holen, sonst int direkt."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = re.search(r"\d+", str(value))
    if m:
        return int(m.group(0))
    return None


def normalize_lsb(
    lsb_raw: Optional[str] = None,
    adr_raw: Optional[Union[str, int]] = None,
    lsb_channel_raw: Optional[Union[str, int]] = None,
    lsb_address_raw: Optional[Union[str, int]] = None,
) -> Optional[str]:
    """
    Normalisiert verschiedene LSB-Schreibweisen zu einem einheitlichen Key.

    Rückgabe z.B.: "LSB1-3" (LSB 1, Adresse 3)
    oder None, wenn nicht bestimmbar.

    Versucht u.a. zu verstehen:
    - "LSBA ( LSB1 ) Adresse 3"
    - "LSB A Adr. 3"
    - "LSB1-3"
    - "LSB_1_3"
    - "LSB 1/3"
    """
    # 1) Falls channel/address explizit übergeben wurden (z.B. aus separaten JSON-Feldern)
    channel = _extract_int(lsb_channel_raw)
    address = _extract_int(lsb_address_raw)

    # 2) Falls noch nicht gesetzt, aus adr_raw holen
    if address is None and adr_raw is not None:
        address = _extract_int(adr_raw)

    # 3) Falls lsb_raw vorhanden, versuchen dort Letter/Ziffern zu finden
    if lsb_raw:
        text = str(lsb_raw)

        # a) "LSBA", "LSB A", "LSB-A" → Letter nach "LSB"
        m_letter = re.search(r"LSB\s*([A-H])", text, re.IGNORECASE)
        if m_letter and channel is None:
            letter = m_letter.group(1).upper()
            channel = LSB_LETTER_TO_NUMBER.get(letter)

        # b) "LSB1", "LSB 1", "LSB-1"
        m_digit = re.search(r"LSB[\s\-_]*([0-9]+)", text, re.IGNORECASE)
        if m_digit and channel is None:
            channel = int(m_digit.group(1))

        # c) Adresse aus Text extrahieren, wenn noch leer
        if address is None:
            # typische Muster: "Adr. 3", "Adresse 3", "/3", "-3", "_3"
            m_adr = re.search(
                r"(Adr\.?|Adresse)\s*([0-9]+)", text, re.IGNORECASE
            )
            if m_adr:
                address = int(m_adr.group(2))
            else:
                # fallback: erste Zahl nach Slash oder Unterstrich
                m_generic = re.search(r"[\/\-_]\s*([0-9]+)", text)
                if m_generic:
                    address = int(m_generic.group(1))

        # d) Manche Texte enthalten "LSB1  Adr. 3" etc. – dort würde oben schon alles gefunden.

    if channel is None or address is None:
        return None

    return f"LSB{channel}-{address}"
