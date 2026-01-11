from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


_SPL_TERMINAL_RE = re.compile(r"\b(X\d{1,4})(?:[\.:/])(\d{1,3})\b", re.IGNORECASE)
_SPL_CONTACT_TOKEN_RE = re.compile(r"\b([A-Z]{1,3}\d{1,4})(?:[/:])(\d{1,3})-(\d{1,3})\b", re.IGNORECASE)


def _normalize_model(value: str) -> str:
    return (value or "").strip()


def _normalize_terminal_ref(value: str) -> str:
    """Normalisiert z.B. X4:9 oder X4.9 -> X4/9 für konsistente Anzeige."""
    s = (value or "").strip().upper()
    m = _SPL_TERMINAL_RE.search(s)
    if not m:
        return s
    return f"{m.group(1).upper()}/{m.group(2)}"


def _extract_primary_bmk_from_result(result: Dict[str, Any]) -> str:
    """Best-effort BMK für LEC Ergebnisse.

    Priorität (wichtig: zuerst die *zugeordnete* Baugruppe, nicht Auto-Extraktion aus LEC-Text):
      1) metadata.sensor_bmk (deterministisch aus LSB→BMK Zuordnung)
      2) result.bmk / metadata.bmk
      3) auto_bmks[0].bmk (nur als Fallback)
      4) 'BMK XYZ' in sensor_name/title
    """
    if not isinstance(result, dict):
        return ""
    meta = result.get("metadata") or {}

    if isinstance(meta, dict):
        bmk = (meta.get("sensor_bmk") or "").strip().upper()
        if bmk:
            return bmk

    bmk_top = (result.get("bmk") or "").strip().upper()
    if bmk_top:
        return bmk_top

    if isinstance(meta, dict):
        bmk = (meta.get("bmk") or "").strip().upper()
        if bmk:
            return bmk

    auto_bmks = result.get("auto_bmks") or (meta.get("auto_bmks") if isinstance(meta, dict) else None)
    if isinstance(auto_bmks, list) and auto_bmks:
        first = auto_bmks[0]
        if isinstance(first, dict):
            bmk = (first.get("bmk") or "").strip().upper()
            if bmk:
                return bmk

    if isinstance(meta, dict):
        sensor_text = str(meta.get("sensor_name") or meta.get("geber_name") or meta.get("title") or "")
        m = re.search(r"BMK\s*([A-Z]\d{1,4}(?:[.\-]\w{1,6})?)", sensor_text, re.IGNORECASE)
        if m:
            return m.group(1).strip().upper()

    return ""


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=64)
def load_spl_references_for_model(models_dir: str, model: str) -> Dict[str, Any]:
    model = _normalize_model(model)
    if not model:
        return {}

    mdir = Path(models_dir) / model
    candidates = [
        mdir / f"{model}_SPL_REFERENCES.json",
        mdir / f"{model}_SPL_REFERENCES",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = _load_json(p)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
    return {}


def spl_pin_hints_for_bmk(models_dir: str, model: str, bmk_code: str) -> Dict[str, Any]:
    """Sammelt Stecker/Pins (terminal_refs) und Kontakte (contact_refs) aus SPL.

    Wichtig: Das ist 'best effort'. Wir verwenden nur eindeutige Co-Occurrences im Kontext,
    um falsche Zuordnungen zu vermeiden.
    """
    model = _normalize_model(model)
    target = (bmk_code or "").strip().upper()
    if not model or not target:
        return {"terminals": [], "contacts": [], "pages": []}

    spl = load_spl_references_for_model(models_dir, model)
    spl_pages = spl.get("spl_pages") if isinstance(spl, dict) else None
    if not isinstance(spl_pages, list):
        return {"terminals": [], "contacts": [], "pages": []}

    terminals: List[str] = []
    contacts: List[str] = []
    connectors: List[str] = []
    pins: List[str] = []
    pages: List[int] = []
    seen_t: set[str] = set()
    seen_c: set[str] = set()
    seen_x: set[str] = set()
    seen_p: set[str] = set()

    def _add_terminal(raw: str) -> None:
        term = _normalize_terminal_ref(raw)
        if not term:
            return
        if term in seen_t:
            return
        seen_t.add(term)
        terminals.append(term)

    def _add_contact(raw: str) -> None:
        c = (raw or "").strip().upper()
        if not c:
            return
        if c in seen_c:
            return
        seen_c.add(c)
        contacts.append(c)

    def _add_connector(raw: str) -> None:
        x = (raw or "").strip().upper()
        if not x:
            return
        if x in seen_x:
            return
        seen_x.add(x)
        connectors.append(x)

    def _add_pin(raw: str) -> None:
        p = (raw or "").strip().upper()
        if not p:
            return
        if p in seen_p:
            return
        seen_p.add(p)
        pins.append(p)

    for page in spl_pages:
        if not isinstance(page, dict):
            continue
        tokens_norm = page.get("tokens_norm") or []
        page_text = str(page.get("text") or "")
        hay = page_text.upper()
        if target not in hay and target not in {str(t).upper() for t in tokens_norm if t}:
            continue

        page_no = page.get("page")
        if isinstance(page_no, int):
            pages.append(page_no)

        # 1) Direkt aus Zeilen mit BMK: dort stehen oft Terminal/Kontakt im selben Fragment
        for ln in page_text.splitlines():
            if target not in ln.upper():
                continue
            for m in _SPL_TERMINAL_RE.finditer(ln):
                _add_terminal(m.group(0))
                if len(terminals) >= 8:
                    break
            for m in _SPL_CONTACT_TOKEN_RE.finditer(ln):
                dev = m.group(1).strip().upper()
                if dev == target:
                    _add_contact(m.group(0))
                    if len(contacts) >= 8:
                        break
            if len(terminals) >= 8 and len(contacts) >= 8:
                break

        for ref in page.get("terminal_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            ctx = str(ref.get("context") or "")
            if target not in ctx.upper():
                continue
            _add_terminal(str(ref.get("terminal") or ""))
            if len(terminals) >= 8:
                break

        for ref in page.get("contact_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            dev = str(ref.get("device") or "").strip().upper()
            if dev != target:
                continue
            raw = str(ref.get("contact_raw") or "").strip().upper()
            if not raw:
                frm = str(ref.get("from") or "").strip()
                to = str(ref.get("to") or "").strip()
                raw = f"{target}/{frm}-{to}" if frm and to else ""
            _add_contact(raw)
            if len(contacts) >= 8:
                break

        # Fallback: OCR-Token + Positionsnaehe (wenn der Kontext-Parser nichts liefert)
        if not terminals and not contacts:
            ocr_tokens = page.get("ocr_tokens") or []
            if isinstance(ocr_tokens, list) and ocr_tokens:
                target_positions: List[tuple[float, float]] = []
                candidates_terminal: List[tuple[float, float, str]] = []
                candidates_contact: List[tuple[float, float, str]] = []

                for tok in ocr_tokens:
                    if not isinstance(tok, dict):
                        continue
                    txt = str(tok.get("text") or "").strip()
                    if not txt:
                        continue
                    x = float(tok.get("x") or 0)
                    y = float(tok.get("y") or 0)
                    w = float(tok.get("w") or 0)
                    h = float(tok.get("h") or 0)
                    cx = x + w / 2.0
                    cy = y + h / 2.0
                    up = txt.upper().replace(" ", "")

                    if up == target or up.startswith(target + "."):
                        target_positions.append((cx, cy))

                    if _SPL_TERMINAL_RE.search(txt):
                        candidates_terminal.append((cx, cy, txt))

                    cm = _SPL_CONTACT_TOKEN_RE.search(txt)
                    if cm and cm.group(1).strip().upper() == target:
                        candidates_contact.append((cx, cy, cm.group(0)))

                if target_positions:
                    # Naehe: im OCR-Bild sind 80..180 px oft "direkt daneben".
                    # Wir nehmen konservativ einen Radius, um nicht quer ueber den Plan zu matchen.
                    radius2 = 160.0 * 160.0

                    def _min_dist2(cx: float, cy: float) -> float:
                        best = 1e18
                        for tx, ty in target_positions:
                            dx = cx - tx
                            dy = cy - ty
                            d2 = dx * dx + dy * dy
                            if d2 < best:
                                best = d2
                        return best

                    for cx, cy, txt in candidates_terminal:
                        if _min_dist2(cx, cy) <= radius2:
                            _add_terminal(txt)
                            if len(terminals) >= 8:
                                break

                    for cx, cy, txt in candidates_contact:
                        if _min_dist2(cx, cy) <= radius2:
                            _add_contact(txt)
                            if len(contacts) >= 8:
                                break

        if len(terminals) >= 8 and len(contacts) >= 8:
            break

    pages = sorted(set(pages))[:6]

    # Fallback: Wenn keine eindeutigen Terminal/Kontakt-Refs gefunden wurden,
    # versuchen wir aus dem globalen Token-Index (bmk_refs) zumindest Stecker/Pins/Signale
    # anzuzeigen (schaltplanbasiert, aber ohne riskante Querzuordnung).
    if not terminals and not contacts:
        refs = spl.get("bmk_refs") if isinstance(spl, dict) else None
        if isinstance(refs, list):
            prefix = target + "."
            for item in refs:
                s = str(item or "").strip().upper()
                if not s.startswith(prefix):
                    continue
                suffix = s[len(prefix):].strip()
                if not suffix:
                    continue

                # Stecker am Bauteil (z.B. A82.X1)
                if re.fullmatch(r"X\d{1,3}", suffix):
                    _add_connector(suffix)
                    continue

                # Pins/Signale (konservativ)
                if re.fullmatch(r"(?:[AE]\d{1,2}|\d{1,2}V|GND|CANH|CANL|LSB|RCAN|CANGND|GNDMESS)", suffix):
                    _add_pin(suffix)

                if len(connectors) >= 6 and len(pins) >= 12:
                    break

            connectors = connectors[:6]

            priority = ["CANH", "CANL", "RCAN", "LSB", "24V", "GND", "CANGND", "GNDMESS"]
            pins = [p for p in priority if p in pins] + [p for p in pins if p not in priority]
            pins = pins[:12]

    return {
        "terminals": terminals,
        "contacts": contacts,
        "connectors": connectors,
        "pins": pins,
        "pages": pages,
    }


def attach_spl_pin_hints(
    results: List[Dict[str, Any]],
    *,
    models_dir: str,
    model_hint: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not results:
        return results

    for r in results:
        if not isinstance(r, dict):
            continue
        explain = r.get("explain")
        if not isinstance(explain, dict):
            continue

        meta = r.get("metadata") or {}
        source_type = (
            (r.get("source_type") or (meta.get("source_type") if isinstance(meta, dict) else "") or "")
            .lower()
            .strip()
        )
        if source_type != "lec_error":
            continue

        model = _normalize_model(r.get("model") or (meta.get("model") if isinstance(meta, dict) else "") or (model_hint or ""))
        bmk = _extract_primary_bmk_from_result(r)
        if not model or not bmk:
            continue

        hints = spl_pin_hints_for_bmk(models_dir, model, bmk)
        terminals = hints.get("terminals") or []
        contacts = hints.get("contacts") or []
        connectors = hints.get("connectors") or []
        pins = hints.get("pins") or []

        steps = explain.get("next_steps")
        if not isinstance(steps, list):
            continue

        added: List[str] = []
        if terminals:
            added.append(f"Schaltplan (SPL): Stecker/Pins zu {bmk}: {', '.join(terminals)}")
        if contacts:
            added.append(f"Schaltplan (SPL): Kontakte an {bmk}: {', '.join(contacts)}")
        if connectors:
            added.append(f"Schaltplan (SPL): Stecker an {bmk}: {', '.join(connectors)}")
        if pins:
            priority = ["CANH", "CANL", "RCAN", "LSB", "24V", "GND", "CANGND", "GNDMESS"]
            core = [p for p in priority if p in pins]
            show = core if core else pins[:8]
            if show:
                added.append(f"Schaltplan (SPL): Versorgung/Bus an {bmk}: {', '.join(show)}")
        if not added:
            continue

        existing = {str(s).strip().lower() for s in steps if str(s).strip()}
        for item in reversed(added):
            if item.strip().lower() in existing:
                continue
            steps.insert(0, item)
        explain["next_steps"] = steps
        r["explain"] = explain

    return results
