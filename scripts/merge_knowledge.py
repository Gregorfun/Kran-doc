# scripts/merge_knowledge.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = BASE_DIR / "output" / "models"


# ----------------------------
# Helpers: JSON
# ----------------------------
def read_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_all_spl_references(model_dir: Path) -> dict:
    files = sorted(model_dir.glob("*_SPL_REFERENCES.json"))
    bmk_set = set()
    sheet_set = set()
    file_names = []

    for fp in files:
        doc = read_json(fp)
        file_names.append(fp.name)

        if isinstance(doc, dict):
            for x in (doc.get("bmk_refs") or []):
                if isinstance(x, str) and x.strip():
                    bmk_set.add(x.strip())
                elif isinstance(x, dict):
                    v = (x.get("bmk") or "").strip()
                    if v:
                        bmk_set.add(v)
            for x in (doc.get("sheet_refs") or []):
                if isinstance(x, str) and x.strip():
                    sheet_set.add(x.strip())
                elif isinstance(x, dict):
                    v = (x.get("sheet_raw") or "").strip()
                    if not v:
                        ref = (x.get("ref") or "").strip()
                        sheet = (x.get("sheet") or "").strip()
                        coord = (x.get("coord") or "").strip()
                        if ref and sheet and coord:
                            v = f"{ref}/{sheet}.{coord}"
                    if v:
                        sheet_set.add(v)
        elif isinstance(doc, list):
            # falls mal als Liste gespeichert wurde
            for x in doc:
                if isinstance(x, str) and x.strip():
                    bmk_set.add(x.strip())

    return {
        "files": file_names,
        "bmk_refs": sorted(bmk_set),
        "sheet_refs": sorted(sheet_set),
    }


# ----------------------------
# Helpers: LSB key parsing
# ----------------------------
LSB_BUS_LETTER_MAP: Dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
}

def normalize_lsb_key(bus: Any, addr: Any) -> Optional[str]:
    try:
        b = int(str(bus).strip())
        a = int(str(addr).strip())
        return f"LSB{b}-{a}"
    except Exception:
        return None


def parse_lsb_from_text(text: str) -> Optional[str]:
    """
    Extrahiert 1 LSB Key aus Text-Varianten:
      - "LSB6-2"
      - "LSB 6 - 2"
      - "LSB B Adr. 24"  -> Bus=B=2 Adr=24
      - "LSB Adr. 2-24"
      - "LSB Adr 2 24"
    """
    if not text:
        return None

    s = str(text)

    # LSB6-2 / LSB 6 - 2
    m = re.search(r"LSB\s*([0-9]+)\s*[-_/ ]\s*([0-9]+)", s, re.IGNORECASE)
    if m:
        return normalize_lsb_key(m.group(1), m.group(2))

    # LSB Adr. 2-24
    m = re.search(r"LSB\s*Adr\.?\s*([0-9]+)\s*[-_/ ]\s*([0-9]+)", s, re.IGNORECASE)
    if m:
        return normalize_lsb_key(m.group(1), m.group(2))

    # LSB Adr 2 24
    m = re.search(r"LSB\s*Adr\.?\s*([0-9]+)\s+([0-9]+)", s, re.IGNORECASE)
    if m:
        return normalize_lsb_key(m.group(1), m.group(2))

    # LSB B Adr. 24
    m = re.search(r"LSB\s*([A-H])\s*(?:Teilnehmer\s*)?Adr\.?\s*([0-9]+)", s, re.IGNORECASE)
    if m:
        letter = m.group(1).upper()
        bus = LSB_BUS_LETTER_MAP.get(letter)
        if bus:
            return normalize_lsb_key(bus, m.group(2))

    return None


def extract_lsb_keys_from_text(text: Any) -> List[str]:
    """
    Extrahiert *mehrere* LSB-Keys aus Freitext (v.a. BMK description),
    inkl. Ranges "2 24-30".
    """
    if text is None:
        return []
    s = str(text).replace("\r", "\n")

    out: List[str] = []

    # direkte Vorkommen (mehrfach möglich)
    for m in re.finditer(r"LSB\s*([0-9]+)\s*[-_/ ]\s*([0-9]+)", s, re.IGNORECASE):
        k = normalize_lsb_key(m.group(1), m.group(2))
        if k:
            out.append(k)

    for m in re.finditer(r"LSB\s*Adr\.?\s*([0-9]+)\s*[-_/ ]\s*([0-9]+)", s, re.IGNORECASE):
        k = normalize_lsb_key(m.group(1), m.group(2))
        if k:
            out.append(k)

    for m in re.finditer(r"LSB\s*Adr\.?\s*([0-9]+)\s+([0-9]+)", s, re.IGNORECASE):
        k = normalize_lsb_key(m.group(1), m.group(2))
        if k:
            out.append(k)

    for m in re.finditer(r"LSB\s*([A-H])\s*(?:Teilnehmer\s*)?Adr\.?\s*([0-9]+)", s, re.IGNORECASE):
        bus = LSB_BUS_LETTER_MAP.get(m.group(1).upper())
        if bus:
            k = normalize_lsb_key(bus, m.group(2))
            if k:
                out.append(k)

    # Range: "2 24-30"
    for m in re.finditer(r"\b([0-9]+)\s+([0-9]+)\s*[-–]\s*([0-9]+)\b", s):
        try:
            bus = int(m.group(1))
            a1 = int(m.group(2))
            a2 = int(m.group(3))
            lo, hi = (a1, a2) if a1 <= a2 else (a2, a1)
            for a in range(lo, hi + 1):
                k = normalize_lsb_key(bus, a)
                if k:
                    out.append(k)
        except Exception:
            pass

    # dedupe
    seen = set()
    uniq: List[str] = []
    for k in out:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq


def lsb_keys_from_bmk_lsb(raw: Any) -> List[str]:
    """
    BMK lsb_address Varianten:
      - "2 24"         -> LSB2-24
      - "2 6 - 9"      -> LSB2-6..LSB2-9
      - "1-8 1"        -> LSB1-1..LSB8-1
      - "LSB2-24"      -> LSB2-24
      - "LSB B Adr. 24"-> LSB2-24
    """
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []

    # direkt aus Text (LSB6-2 oder LSB B Adr. 24)
    k = parse_lsb_from_text(s)
    if k:
        return [k]

    # "2 24"
    m = re.match(r"^\s*([0-9]+)\s+([0-9]+)\s*$", s)
    if m:
        k = normalize_lsb_key(m.group(1), m.group(2))
        return [k] if k else []

    # "2 6 - 9"
    m = re.match(r"^\s*([0-9]+)\s+([0-9]+)\s*[-–]\s*([0-9]+)\s*$", s)
    if m:
        bus = int(m.group(1))
        a1 = int(m.group(2))
        a2 = int(m.group(3))
        lo, hi = (a1, a2) if a1 <= a2 else (a2, a1)
        out = []
        for a in range(lo, hi + 1):
            k2 = normalize_lsb_key(bus, a)
            if k2:
                out.append(k2)
        return out

    # "1-8 1" (bus range, one address)
    m = re.match(r"^\s*([0-9]+)\s*[-–]\s*([0-9]+)\s+([0-9]+)\s*$", s)
    if m:
        b1 = int(m.group(1))
        b2 = int(m.group(2))
        adr = int(m.group(3))
        lo, hi = (b1, b2) if b1 <= b2 else (b2, b1)
        out = []
        for b in range(lo, hi + 1):
            k2 = normalize_lsb_key(b, adr)
            if k2:
                out.append(k2)
        return out

    return []


# ----------------------------
# BMK loader (OW/UW oder Combined)
# ----------------------------
def _extract_components_from_bmk_doc(doc: Any) -> List[Dict[str, Any]]:
    """
    Unterstützt gängige Formate:
      - {"components": [ ... ]}
      - {"items": [ ... ]}
      - {"data": [ ... ]}
      - [ ... ] (Liste direkt)
    """
    if doc is None:
        return []
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if isinstance(doc, dict):
        for key in ("components", "items", "data"):
            v = doc.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def load_bmk_blocks(model_dir: Path, model: str) -> Dict[str, Dict[str, Any]]:
    """
    Liefert Blocks:
      {
        "oberwagen": {"components": [...]},
        "unterwagen": {"components": [...]}
      }
    Akzeptiert:
      - {model}_BMK_OW.json + {model}_BMK_UW.json
      - ODER {model}_BMK.json (combined)
    """
    ow = read_json(model_dir / f"{model}_BMK_OW.json")
    uw = read_json(model_dir / f"{model}_BMK_UW.json")
    combined = read_json(model_dir / f"{model}_BMK.json")

    blocks: Dict[str, Dict[str, Any]] = {}

    ow_comps = _extract_components_from_bmk_doc(ow)
    uw_comps = _extract_components_from_bmk_doc(uw)
    if ow_comps:
        blocks["oberwagen"] = {"components": ow_comps}
    if uw_comps:
        blocks["unterwagen"] = {"components": uw_comps}

    if blocks:
        return blocks

    comb_comps = _extract_components_from_bmk_doc(combined)
    if comb_comps:
        ow_list: List[Dict[str, Any]] = []
        uw_list: List[Dict[str, Any]] = []
        unk_list: List[Dict[str, Any]] = []

        for c in comb_comps:
            wagon = str(c.get("wagon") or c.get("_wagon") or "").strip().lower()
            if "ober" in wagon:
                ow_list.append(c)
            elif "unter" in wagon:
                uw_list.append(c)
            else:
                unk_list.append(c)

        if not ow_list and not uw_list and unk_list:
            ow_list = unk_list
            unk_list = []

        if ow_list:
            blocks["oberwagen"] = {"components": ow_list}
        if uw_list:
            blocks["unterwagen"] = {"components": uw_list}
        if unk_list:
            blocks["unknown"] = {"components": unk_list}

    return blocks


def build_bmk_lsb_index(blocks: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Index: LSB-Key -> Liste von BMK-Kandidaten

    Hinweis:
    - Der Index kann mehrere Kandidaten pro LSB enthalten.
    - Konsumenten (UI/Enrichment) nehmen ab jetzt deterministisch nur den ersten (=besten) Kandidaten.
    """
    idx: Dict[str, List[Dict[str, Any]]] = {}

    for block_name, block in blocks.items():
        comps = block.get("components") or []
        if not isinstance(comps, list):
            continue

        for c in comps:
            if not isinstance(c, dict):
                continue

            raw_lsb = c.get("lsb_address") or c.get("lsb") or c.get("lsb_key")
            keys = lsb_keys_from_bmk_lsb(raw_lsb)

            # FALLBACK: LSB aus description/Text
            if not keys:
                keys = extract_lsb_keys_from_text(c.get("description") or "")

            if not keys:
                continue

            bmk = c.get("bmk") or c.get("code") or c.get("bmk_code")
            title = c.get("title") or c.get("name")
            desc = c.get("description")

            entry = {
                "bmk": bmk,
                "title": title,
                "description": desc,
                "wagon": c.get("wagon") or block_name,
                "area": c.get("area"),
                "group": c.get("group"),
                "lsb_address": raw_lsb,
            }

            for k in keys:
                idx.setdefault(k, []).append(entry)

    return idx


def summarize_bmk(entry: Dict[str, Any]) -> str:
    bmk = (entry.get("bmk") or "").strip()
    title = (entry.get("title") or "").strip()
    if bmk and title:
        return f"BMK {bmk}, {title}"
    if bmk:
        return f"BMK {bmk}"
    if title:
        return title
    return "BMK Treffer"


def _shorten_text(text: Any, max_len: int = 400) -> str:
    if not text:
        return ""
    s = str(text).strip()
    if len(s) <= max_len:
        return s
    return s[:max_len].rstrip()


# ----------------------------
# Merge pro Modell
# ----------------------------
def merge_model(model: str) -> None:
    model_dir = MODELS_DIR / model

    lec_path = model_dir / f"{model}_LEC_ERRORS.json"
    lec_doc = read_json(lec_path)
    lec_errors: List[Dict[str, Any]] = []

    if isinstance(lec_doc, dict) and isinstance(lec_doc.get("errors"), list):
        lec_errors = [e for e in lec_doc["errors"] if isinstance(e, dict)]
    elif isinstance(lec_doc, list):
        lec_errors = [e for e in lec_doc if isinstance(e, dict)]
    elif isinstance(lec_doc, dict) and isinstance(lec_doc.get("data"), list):
        lec_errors = [e for e in lec_doc["data"] if isinstance(e, dict)]

    # BMK
    bmk_blocks = load_bmk_blocks(model_dir, model)
    bmk_index = build_bmk_lsb_index(bmk_blocks)

    spl_references = load_all_spl_references(model_dir)

    # SPL-References
    spl_doc = read_json(model_dir / f"{model}_SPL_REFERENCES.json")
    spl_chunks: List[Dict[str, Any]] = []
    spl_pages = spl_doc.get("spl_pages") if isinstance(spl_doc, dict) else []
    spl_pdf = spl_doc.get("source_file") if isinstance(spl_doc, dict) else ""
    if isinstance(spl_pages, list):
        for page in spl_pages:
            if not isinstance(page, dict):
                continue
            spl_chunks.append(
                {
                    "model": model,
                    "source_type": "spl_reference",
                    "page": page.get("page"),
                    "title": page.get("title") or "",
                    "tokens": page.get("tokens") or [],
                    "text": _shorten_text(page.get("text")),
                    "pdf_file": spl_pdf,
                }
            )

    spl_files = spl_references.get("files") if isinstance(spl_references, dict) else []
    spl_source_file = spl_files[0] if isinstance(spl_files, list) and spl_files else None

    for ref in spl_references.get("bmk_refs", []) if isinstance(spl_references, dict) else []:
        if not ref:
            continue
        spl_chunks.append(
            {
                "model": model,
                "source_type": "spl_reference",
                "title": "Schaltplan-Referenz",
                "text": f"SPL Referenz: {ref}",
                "tokens": [ref],
            }
        )

    for item in spl_references.get("sheet_refs", []) if isinstance(spl_references, dict) else []:
        ref = ""
        if isinstance(item, dict):
            ref = item.get("sheet_raw") or ""
            if not ref:
                ref = f"{item.get('ref', '')}/{item.get('sheet', '')}.{item.get('coord', '')}".strip()
        if not ref:
            ref = str(item).strip()
        if not ref:
            continue
        spl_chunks.append(
            {
                "model": model,
                "source_type": "spl_reference",
                "title": "Schaltplan-Referenz",
                "text": f"SPL Referenz: {ref}",
                "tokens": [ref],
            }
        )

    for chunk in spl_chunks:
        st = chunk.get("source_type")
        if isinstance(st, str) and st.lower() == "spl_reference":
            chunk["source_type"] = "spl_reference"

    # Handbücher (optional, aktuell 0 – bleibt so, bis manual-parser existiert)
    handbook_samples: List[Dict[str, Any]] = []

    # LEC -> BMK Links (NEU: nur 1 BMK Link)
    lec_with_bmk = 0
    for e in lec_errors:
        # Wichtig: erst vorhandenes lsb_key nutzen (bei dir vorhanden!)
        lsb_key = (e.get("lsb_key") or "").strip()
        if not lsb_key:
            short = e.get("short_text") or ""
            longt = e.get("long_text") or ""
            raw_lsb = e.get("lsb_address") or e.get("lsb") or ""

            lsb_key = (
                parse_lsb_from_text(str(raw_lsb))
                or parse_lsb_from_text(str(short))
                or parse_lsb_from_text(str(longt))
                or ""
            )

        if not lsb_key:
            continue

        hits = bmk_index.get(lsb_key, [])
        if not hits:
            continue

        lec_with_bmk += 1

        # deterministisch: "best" = erster Treffer
        best = hits[0]

        # Kompatibel + besser:
        e["lsb_error_key"] = lsb_key

        # NEU: nur 1 Treffer (statt Liste)
        e["bmk_link"] = best

        # Optional: Count behalten (für Stats/Debug)
        e["bmk_links_count"] = len(hits)

        # Kompakte Anzeige
        e["bmk_summary"] = summarize_bmk(best)

        # ALT (entfernt): e["bmk_links"] = hits

    # FULL_KNOWLEDGE
    full_legacy = {
        "model": model,
        "handbook_samples": handbook_samples,
        "lec_errors": lec_errors,
        "bmk_blocks": bmk_blocks,
        "spl_references": spl_references,
        "knowledge_chunks": spl_chunks,
        "bmk_lsb_index_size": len(bmk_index),
        "stats": {
            "handbook_samples": len(handbook_samples),
            "lec_errors": len(lec_errors),
            "bmk_blocks": len(bmk_blocks),
            "bmk_lsb_keys": len(bmk_index),
            "lec_with_bmk": lec_with_bmk,
            "spl_files": len(spl_references.get("files", [])),
            "spl_bmk_refs": len(spl_references.get("bmk_refs", [])),
            "spl_sheet_refs": len(spl_references.get("sheet_refs", [])),
        },
    }

    full_gpt51 = {
        "model": model,
        "meta": {"format": "GPT51_FULL_KNOWLEDGE"},
        **full_legacy,
        "spl_references": spl_references,
    }

    out_legacy = model_dir / f"{model}_FULL_KNOWLEDGE.json"
    out_gpt51 = model_dir / f"{model}_GPT51_FULL_KNOWLEDGE.json"
    write_json(out_legacy, full_legacy)
    write_json(out_gpt51, full_gpt51)

    # Print Report
    print(f"\n[MODEL] {model}")
    print(f"   Samples (Handbuch): {len(handbook_samples)}")
    print(f"   LEC-Fehler:         {len(lec_errors)}")
    print(f"   BMK-Blocks:         {len(bmk_blocks)}")
    print(f"   BMK-LSB-Keys:       {len(bmk_index)}")
    print(f"   SPL-Files:          {len(spl_references.get('files', []))}")
    print(f"   SPL-BMK-Refs:       {len(spl_references.get('bmk_refs', []))}")
    print(f"   SPL-Sheet-Refs:     {len(spl_references.get('sheet_refs', []))}")
    print(f"   LEC mit BMK-Link:   {lec_with_bmk}")
    print(f"   -> FULL_KNOWLEDGE (GPT51) geschrieben: {out_gpt51}")
    print(f"   -> FULL_KNOWLEDGE (legacy) geschrieben: {out_legacy}")


def main() -> None:
    if not MODELS_DIR.exists():
        print(f"[ERROR] models dir not found: {MODELS_DIR}")
        return

    models = sorted([p.name for p in MODELS_DIR.iterdir() if p.is_dir()])
    if not models:
        print("[WARN] No model folders found.")
        return

    for m in models:
        merge_model(m)


if __name__ == "__main__":
    main()
