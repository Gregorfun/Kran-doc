from __future__ import annotations

import json
import os
import re
import uuid
# --- NEW ---
import hashlib
from datetime import datetime
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Iterator

# Basis-Pfade
BASE_DIR = Path(__file__).resolve().parents[1]  # .../kran-tools
MODELS_DIR = BASE_DIR / "output" / "models"
OUT_CHUNKS = BASE_DIR / "output" / "embeddings" / "knowledge_chunks.jsonl"

bmk_freq = Counter()
BMK_TOKEN_RE = re.compile(r"\b[A-Z]{1,3}\d{1,4}\*?\b")

# --- NEW ---
DEDUPE_HASHES: set[str] = set()
DEDUPE_SKIPPED = 0
META_ID_SOURCES: Dict[str, str] = {}
CHUNKS_BY_LAYER: Dict[str, int] = {}
WRITTEN_CHUNKS = 0
SOURCE_FILES: List[str] = []


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


SPL_BMK_LIMIT = _env_int("KRANDOC_SPL_BMK_LIMIT", 2000)
SPL_SHEET_LIMIT = _env_int("KRANDOC_SPL_SHEET_LIMIT", 2000)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Windows/UTF-8-BOM Fallback
        return json.loads(path.read_text(encoding="utf-8-sig"))

# --- NEW ---
def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())

# --- NEW ---
def _hash_key(text: str, layer: str, topic: str) -> str:
    payload = _normalize_text(text) + (layer or "") + (topic or "")
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

# --- NEW ---
def _validate_meta_id(meta_id: Any, source_info: str) -> None:
    if meta_id is None:
        return
    meta_id_str = str(meta_id)
    if meta_id_str in META_ID_SOURCES:
        prev = META_ID_SOURCES[meta_id_str]
        print(f"[ERROR] Duplicate meta id '{meta_id_str}' from {source_info}; already seen from {prev}")
        raise SystemExit(1)
    META_ID_SOURCES[meta_id_str] = source_info

# --- NEW ---
def _maybe_write_obj(out_file, obj: Dict[str, Any], source_info: str) -> bool:
    global DEDUPE_SKIPPED, WRITTEN_CHUNKS
    text = (obj.get("text") or "").strip()
    if not text:
        return False
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    layer = str(metadata.get("layer") or "")
    topic = str(metadata.get("topic") or "")
    _validate_meta_id(metadata.get("id"), source_info)
    h = _hash_key(text, layer, topic)
    if h in DEDUPE_HASHES:
        DEDUPE_SKIPPED += 1
        return False
    DEDUPE_HASHES.add(h)
    out_file.write(json.dumps(obj, ensure_ascii=False) + "\n")
    WRITTEN_CHUNKS += 1
    layer_key = layer or "unknown"
    CHUNKS_BY_LAYER[layer_key] = CHUNKS_BY_LAYER.get(layer_key, 0) + 1
    return True

def load_liccon_general_cards(base_dir: Path) -> List[Dict[str, Any]]:
    path = base_dir / "output" / "general" / "liccon_general_starterpack.json"
    if not path.exists():
        print(f"[WARN] LICCON general starterpack fehlt: {path}")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] LICCON general starterpack ungültig: {path} ({e})")
        return []
    # --- NEW ---
    if str(path) not in SOURCE_FILES:
        SOURCE_FILES.append(str(path))
    if not isinstance(data, dict):
        print(f"[WARN] LICCON general starterpack: JSON-Root ist kein Objekt: {path}")
        return []
    cards = data.get("cards") or []
    if not isinstance(cards, list):
        print(f"[WARN] LICCON general starterpack: 'cards' ist keine Liste: {path}")
        return []
    return [c for c in cards if isinstance(c, dict)]

def cards_to_chunks(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for card in cards:
        title = (card.get("title") or "").strip()
        summary = (card.get("summary") or "").strip()
        steps = card.get("steps") if isinstance(card.get("steps"), list) else []
        tags = card.get("tags") if isinstance(card.get("tags"), list) else []
        source = card.get("source") if isinstance(card.get("source"), dict) else {}

        lines: List[str] = []
        if title:
            lines.append(title)
        if summary:
            lines.append(summary)
        if steps:
            cleaned_steps = [str(s).strip() for s in steps if str(s).strip()]
            if cleaned_steps:
                lines.append("Schritte:")
                lines.extend([f"- {s}" for s in cleaned_steps])
        if tags:
            cleaned_tags = [str(t).strip() for t in tags if str(t).strip()]
            if cleaned_tags:
                lines.append("Tags: " + ", ".join(cleaned_tags))
        if source:
            pdf = source.get("pdf")
            pages = source.get("pages")
            if pdf or pages:
                parts = []
                if pdf:
                    parts.append(str(pdf).strip())
                if pages:
                    parts.append(str(pages).strip())
                if parts:
                    lines.append("Quelle: " + " ".join(parts))

        text = "\n".join(lines).strip()
        if not text:
            continue

        meta: Dict[str, Any] = {
            "layer": "liccon_general",
            "topic": card.get("topic"),
            "severity_hint": card.get("severity_hint"),
            "source": source,
            "title": card.get("title"),
            "id": card.get("id"),
        }
        chunks.append({"text": text, "meta": meta})

    return chunks


def find_full_knowledge_files() -> List[Path]:
    """
    Sucht alle *_GPT51_FULL_KNOWLEDGE.json bzw. *_FULL_KNOWLEDGE.json
    in den Modell-Ordnern.
    """
    files: List[Path] = []
    if not MODELS_DIR.exists():
        return files

    for model_dir in MODELS_DIR.iterdir():
        if not model_dir.is_dir():
            continue

        # neue Variante zuerst
        gpt51_files = list(model_dir.glob("*_GPT51_FULL_KNOWLEDGE.json"))
        if gpt51_files:
            files.extend(gpt51_files)
            continue

        # Fallback: alte Variante
        legacy_files = list(model_dir.glob("*_FULL_KNOWLEDGE.json"))
        files.extend(legacy_files)

    return files


def new_chunk_id() -> str:
    return str(uuid.uuid4())


def write_chunk(
    out_file,
    model: str,
    source: str,
    text: str,
    meta: Dict[str, Any] | None = None,
) -> None:
    """
    Struktur kompatibel zur Webapp halten:

    {
      "id": "...",
      "text": "...",
      "metadata": {
         "model": "...",
         "source": "...",
         ...    # weitere Felder
      }
    }
    """
    text = (text or "").strip()
    if not text:
        return

    metadata: Dict[str, Any] = {"model": model, "source": source}
    if meta:
        metadata.update(meta)

    obj: Dict[str, Any] = {
        "id": new_chunk_id(),
        "text": text,
        "metadata": metadata,
    }

    # --- NEW ---
    _maybe_write_obj(out_file, obj, f"model={model} source={source}")


def clean_bmk_description(desc: Any) -> str:
    """
    BMK-Beschreibung bereinigen:
    - alles ab "LSB Adr" / "LSB" in vielen PDFs wegschneiden (optional)
    - Tokens wie "liebherr", "Ersteller: lwenep0" entfernen
    """
    if desc is None:
        return ""
    s = str(desc).strip()
    if not s:
        return ""

    # Schneide ab "LSB Adr" (häufig kommt danach nur Adress-/Footer-Müll)
    cut_markers = [
        "\nLSB Adr",
        "\nLSB ADR",
        "\nLSB Adr.",
        "\nLSB ADR.",
        "\nLSB ",
        "\nLSB\t",
    ]
    for m in cut_markers:
        idx = s.find(m)
        if idx > 0:
            s = s[:idx].strip()
            break

    # Entferne Liebherr + Ersteller/IDs
    # Beispiel: "Ersteller: lweeng1 / Ausgabe: 02.10.2020"
    s = re.sub(r"(?im)\bliebherr\b.*$", "", s).strip()
    s = re.sub(r"(?im)\bersteller:\s*[a-z0-9_/-]+\s*(/.*)?$", "", s).strip()
    s = re.sub(r"(?im)\bersteller:\s*[a-z0-9_/-]+.*", "", s).strip()

    # Mehrfach-Leerzeilen reduzieren
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def bump_bmk_freq_from_text(text: str) -> None:
    if not text:
        return
    for tok in BMK_TOKEN_RE.findall(text.upper()):
        bmk_freq[tok] += 1


# ---------------------------------------------------------------------------
# Export: MANUALS
# ---------------------------------------------------------------------------

def export_manuals(data: Dict[str, Any], model: str, out_file, model_bmk_freq: Counter) -> int:
    # unterstützt mehrere mögliche Keys
    samples = (
        data.get("samples")
        or data.get("manual_entries")
        or data.get("handbook_samples")
        or []
    )
    if not isinstance(samples, list):
        samples = []

    count = 0
    for entry in samples:
        if not isinstance(entry, dict):
            continue
        txt = (entry.get("text") or entry.get("content") or "").strip()
        if not txt:
            continue

        for tok in BMK_TOKEN_RE.findall((txt or "").upper()):
            model_bmk_freq[tok] += 1

        meta = {"section": entry.get("section") or entry.get("title")}
        bump_bmk_freq_from_text(txt)
        write_chunk(out_file, model=model, source="manual", text=txt, meta=meta)
        count += 1

    print(f"   [MANUAL] Sektionen: {count}")
    return count


# ---------------------------------------------------------------------------
# Export: LEC-Fehler
# ---------------------------------------------------------------------------

def resolve_lec_list(data: Any) -> List[Dict[str, Any]]:
    """
    Holt eine LEC-Liste aus möglichen Strukturen:
      - {"errors": [ ... ]}
      - {"data":  [ ... ]}
      - [ ... ]
      - None -> []
    """
    if data is None:
        return []
    if isinstance(data, dict):
        v = data.get("errors") or data.get("data") or []
        return v if isinstance(v, list) else []
    if isinstance(data, list):
        return data
    return []


def export_lec_errors(data: Dict[str, Any], model: str, out_file, model_bmk_freq: Counter) -> int:
    """
    1. Zeile im Text = NUR der Fehlercode (z.B. '1A3153')
    Danach Kurztext, Langtext, und optional LSB/BMK-Info.
    """
    lec_list = resolve_lec_list(data.get("lec_errors"))
    count = 0

    for err in lec_list:
        if not isinstance(err, dict):
            continue

        code = (err.get("code") or err.get("error_code") or "").strip()
        short_text = (err.get("short_text") or err.get("title") or "").strip()
        long_text = (err.get("long_text") or err.get("description") or "").strip()

        # Merge_knowledge setzt häufig lsb_error_key + bmk_summary
        lsb_key = (
            err.get("lsb_error_key")
            or err.get("lsb_key")
            or err.get("lsb_address")
            or err.get("lsb")
        )
        bmk_summary = err.get("bmk_summary")

        lines: List[str] = []

        # 1. Zeile: nur der Code
        if code:
            lines.append(code)

        # 2. Zeile: Kurztext
        if short_text:
            lines.append(short_text)

        # 3. Zeile: Langtext
        if long_text:
            lines.append(long_text)

        # Zusatzinfos
        if lsb_key:
            lines.append(f"LSB: {lsb_key}")
        if bmk_summary:
            lines.append(f"BMK / Geber / Ort: {bmk_summary}")

        txt = "\n".join(lines).strip()
        if not txt:
            continue

        for tok in BMK_TOKEN_RE.findall((txt or "").upper()):
            model_bmk_freq[tok] += 1

        meta: Dict[str, Any] = {
            "error_code": code,
            "source_type": "lec_error",
        }
        if lsb_key:
            meta["lsb_key"] = lsb_key
        if bmk_summary:
            meta["has_bmk_link"] = True

        bump_bmk_freq_from_text(txt)
        write_chunk(out_file, model=model, source="lec_error", text=txt, meta=meta)
        count += 1

    print(f"   [LEC] Fehler: {count}")
    return count


# ---------------------------------------------------------------------------
# Export: BMK-Komponenten
#   - neu: bmk_blocks (dict) aus FULL_KNOWLEDGE
#   - fallback: bmk_data (alt)
# ---------------------------------------------------------------------------

def iter_bmk_components(data: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """
    Unterstützt mehrere FULL_KNOWLEDGE-Formate:
      A) Neu: bmk_blocks = { "oberwagen": {"components":[...]}, ... }
      B) Alt: bmk_data   = [ { "components":[...] }, ... ]
      C) Sonstiges: bmk_components (list) / components (list)
    """
    # A) Neu: bmk_blocks
    blocks = data.get("bmk_blocks")
    if isinstance(blocks, dict):
        for wagon, block in blocks.items():
            if not isinstance(block, dict):
                continue
            comps = block.get("components")
            if isinstance(comps, list):
                for c in comps:
                    if isinstance(c, dict):
                        cc = dict(c)
                        cc.setdefault("wagon", wagon)
                        yield cc
        return

    # B) Alt: bmk_data
    bmk_blocks_list = data.get("bmk_data") or []
    if isinstance(bmk_blocks_list, list):
        for block in bmk_blocks_list:
            if not isinstance(block, dict):
                continue
            comps = block.get("components")
            if isinstance(comps, list):
                for c in comps:
                    if isinstance(c, dict):
                        yield c
        return

    # C) Fallback: direkte Liste
    direct = data.get("bmk_components") or data.get("components") or []
    if isinstance(direct, list):
        for c in direct:
            if isinstance(c, dict):
                yield c


def export_bmk_components(data: Dict[str, Any], model: str, out_file, model_bmk_freq: Counter) -> int:
    components = list(iter_bmk_components(data))
    count = 0

    for comp in components:
        bmk = (comp.get("bmk") or comp.get("tag") or comp.get("kennzeichen") or comp.get("code") or "").strip()
        title = (comp.get("title") or comp.get("sensor_name") or comp.get("name") or "").strip()

        # Wichtig: description extra anzeigen (kurzer Verbraucher-/Name-Text)
        descr_raw = comp.get("description")
        descr = clean_bmk_description(descr_raw) if descr_raw else ""
        if not descr and title:
            # wenn description leer ist, nutzen wir title als sinnvolle Kurzinfo
            descr = title

        wagon = (comp.get("wagon") or comp.get("_wagon") or "").strip()
        area = (comp.get("area") or comp.get("location") or comp.get("ort") or comp.get("einbauort") or "").strip()
        group = (comp.get("group") or comp.get("module") or comp.get("modul") or "").strip()
        lsb_addr = comp.get("lsb_address") or comp.get("lsb") or comp.get("lsb_key")
        sheet = (comp.get("sheet") or comp.get("blatt") or "").strip()

        lines: List[str] = []
        if bmk:
            lines.append(f"BMK: {bmk}")
        if descr:
            lines.append(f"Beschreibung: {descr}")
        if wagon:
            lines.append(f"Wagen: {wagon}")
        if area:
            lines.append(f"Ort/Bereich: {area}")
        if group:
            lines.append(f"Gruppe/Modul: {group}")
        if lsb_addr:
            lines.append(f"LSB-Adresse: {lsb_addr}")
        if sheet:
            lines.append(f"Blatt: {sheet}")

        txt = "\n".join(lines).strip()
        if not txt:
            continue

        for tok in BMK_TOKEN_RE.findall((txt or "").upper()):
            model_bmk_freq[tok] += 1

        meta: Dict[str, Any] = {
            "bmk": bmk or None,
            "source_type": "bmk",
        }
        if wagon:
            meta["wagon"] = wagon
        if area:
            meta["location"] = area
        if group:
            meta["module"] = group
        if lsb_addr:
            meta["lsb_address"] = lsb_addr

        bump_bmk_freq_from_text(txt)
        write_chunk(out_file, model=model, source="bmk", text=txt, meta=meta)
        count += 1

    print(f"   [BMK] Komponenten: {count}")
    return count


# ---------------------------------------------------------------------------
# Export: BMK-LINKS (Fehlercode + BMK Summary)
# ---------------------------------------------------------------------------

def export_bmk_links(data: Dict[str, Any], model: str, out_file) -> int:
    """
    Exportiert LEC->BMK Verknüpfungen für Embeddings.

    In eurem Merge ist:
      - bmk_links = int (Anzahl)
      - bmk_summary = string (wichtigster Text)
      - lsb_error_key = "LSB2-24" etc.
    """
    lec_errors = data.get("lec_errors") or []
    if not isinstance(lec_errors, list):
        return 0

    count = 0

    for e in lec_errors:
        if not isinstance(e, dict):
            continue

        code = (e.get("error_code") or e.get("code") or "").strip()
        if not code:
            continue

        bmk_summary = (e.get("bmk_summary") or "").strip()
        if not bmk_summary:
            continue

        lsb_key = (
            e.get("lsb_error_key")
            or e.get("lsb_key")
            or e.get("lsb_address")
            or e.get("lsb")
        )

        lines = [
            f"{code}",  # 1. Zeile = Fehlercode
            f"BMK-Link: {bmk_summary}",
        ]
        if lsb_key:
            lines.append(f"LSB: {lsb_key}")

        txt = "\n".join(lines).strip()

        meta: Dict[str, Any] = {
            "error_code": code,
            "source_type": "lec_bmk_link",
            "has_bmk_link": True,
        }
        if lsb_key:
            meta["lsb_key"] = lsb_key

        bump_bmk_freq_from_text(txt)
        write_chunk(out_file, model=model, source="lec_bmk_link", text=txt, meta=meta)
        count += 1

    print(f"   [LINKS] LEC→BMK: {count}")
    return count


# ---------------------------------------------------------------------------
# Export: SPL-Referenzen
# ---------------------------------------------------------------------------

def export_spl_references(data: Dict[str, Any], model: str, out_file) -> int:
    spl = (data.get("spl_references") or {})
    if not isinstance(spl, dict):
        return 0

    bmk_refs = [r.upper() for r in (spl.get("bmk_refs") or []) if isinstance(r, str) and r.strip()]
    bmk_refs = sorted(set(bmk_refs))
    bmk_refs.sort(key=lambda r: (bmk_freq.get(r, 0), r), reverse=True)
    if SPL_BMK_LIMIT > 0:
        bmk_refs = bmk_refs[:SPL_BMK_LIMIT]

    sheet_refs = [r.strip() for r in (spl.get("sheet_refs") or []) if isinstance(r, str) and r.strip()]
    if SPL_SHEET_LIMIT > 0:
        sheet_refs = sheet_refs[:SPL_SHEET_LIMIT]

    seen: set[tuple[str, str]] = set()
    count = 0

    def write_spl_chunk(ref: str, kind: str) -> None:
        chunk_id = f"{model}:spl:{kind}:{ref}"
        meta = {
            "source_type": "spl_reference",
            "title": "Schaltplan",
            "ref": ref,
            "kind": kind,
        }
        obj = {
            "id": chunk_id,
            "text": f"SPL {'BMK' if kind == 'bmk_ref' else 'Sheet'}: {ref}",
            "metadata": {"model": model, "source": "spl_reference", **meta},
        }
        # --- NEW ---
        _maybe_write_obj(out_file, obj, f"model={model} source=spl_reference")

    for ref in bmk_refs:
        key = ("bmk_ref", ref)
        if key in seen:
            continue
        seen.add(key)
        write_spl_chunk(ref, "bmk_ref")
        count += 1

    for ref in sheet_refs:
        key = ("sheet_ref", ref)
        if key in seen:
            continue
        seen.add(key)
        write_spl_chunk(ref, "sheet_ref")
        count += 1

    return count


# ---------------------------------------------------------------------------
# Haupt-Export
# ---------------------------------------------------------------------------

def export() -> None:
    print("=== EXPORT FOR EMBEDDINGS ===")

    # --- NEW ---
    global DEDUPE_HASHES, DEDUPE_SKIPPED, META_ID_SOURCES, CHUNKS_BY_LAYER, WRITTEN_CHUNKS, SOURCE_FILES
    DEDUPE_HASHES = set()
    DEDUPE_SKIPPED = 0
    META_ID_SOURCES = {}
    CHUNKS_BY_LAYER = {}
    WRITTEN_CHUNKS = 0
    SOURCE_FILES = []

    files = find_full_knowledge_files()
    print(f"[INFO] FULL_KNOWLEDGE-Dateien gefunden: {len(files)}")

    OUT_CHUNKS.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0

    with OUT_CHUNKS.open("w", encoding="utf-8") as out:
        for fk in files:
            data = load_json(fk)
            if not isinstance(data, dict):
                continue

            model_bmk_freq = Counter()
            model = data.get("model") or fk.parent.name
            print(f"\n[MODEL] {model}  ({fk.name})")
            if str(model).lower().startswith("spl_"):
                print("   [SKIP] SPL-Dokument-Ordner (kein Kranmodell)")
                continue

            total_chunks += export_manuals(data, model, out, model_bmk_freq)
            total_chunks += export_lec_errors(data, model, out, model_bmk_freq)
            total_chunks += export_bmk_components(data, model, out, model_bmk_freq)
            total_chunks += export_bmk_links(data, model, out)

            spl = (data.get("spl_references") or {})
            bmk_refs = spl.get("bmk_refs") or []
            sheet_refs = spl.get("sheet_refs") or []

            # normalize + dedupe BMK refs
            norm_bmk = []
            for r in bmk_refs:
                if isinstance(r, str) and r.strip():
                    norm_bmk.append(r.strip().upper())
            norm_bmk = sorted(set(norm_bmk))

            # rank BMK refs by frequency in this model's exported texts
            norm_bmk.sort(key=lambda r: (model_bmk_freq.get(r, 0), r), reverse=True)

            # apply limit (default 2000)
            SPL_BMK_LIMIT = int((os.getenv("KRANDOC_SPL_BMK_LIMIT") or "2000").strip() or "2000")
            if SPL_BMK_LIMIT > 0:
                norm_bmk = norm_bmk[:SPL_BMK_LIMIT]

            # sheet refs (usually small) - optional separate limit
            norm_sheet = []
            for r in sheet_refs:
                if isinstance(r, str) and r.strip():
                    norm_sheet.append(r.strip())
            norm_sheet = sorted(set(norm_sheet))

            SPL_SHEET_LIMIT = int((os.getenv("KRANDOC_SPL_SHEET_LIMIT") or "2000").strip() or "2000")
            if SPL_SHEET_LIMIT > 0:
                norm_sheet = norm_sheet[:SPL_SHEET_LIMIT]

            # create chunks
            for ref in norm_bmk:
                obj = {
                    "id": f"{model}:spl:bmk:{ref}",
                    "model": model,
                    "source_type": "spl_reference",
                    "title": "Schaltplan",
                    "text": f"SPL BMK: {ref}",
                    "metadata": {
                        "model": model,
                        "source": "spl_reference",
                        "source_type": "spl_reference",
                        "title": "Schaltplan",
                        "ref": ref,
                        "kind": "bmk_ref",
                    },
                }
                # --- NEW ---
                if _maybe_write_obj(out, obj, f"model={model} source=spl_reference"):
                    total_chunks += 1

            for ref in norm_sheet:
                obj = {
                    "id": f"{model}:spl:sheet:{ref}",
                    "model": model,
                    "source_type": "spl_reference",
                    "title": "Schaltplan",
                    "text": f"SPL Sheet: {ref}",
                    "metadata": {
                        "model": model,
                        "source": "spl_reference",
                        "source_type": "spl_reference",
                        "title": "Schaltplan",
                        "ref": ref,
                        "kind": "sheet_ref",
                    },
                }
                # --- NEW ---
                if _maybe_write_obj(out, obj, f"model={model} source=spl_reference"):
                    total_chunks += 1

            print(f"   [SPL] export BMK: {len(norm_bmk)}  Sheet: {len(norm_sheet)}")

        liccon_cards = load_liccon_general_cards(BASE_DIR)
        liccon_chunks = cards_to_chunks(liccon_cards)
        for chunk in liccon_chunks:
            if _maybe_write_obj(
                out,
                {
                    "id": new_chunk_id(),
                    "text": chunk["text"],
                    "metadata": {"model": "general", "source": "liccon_general", **chunk["meta"]},
                },
                "model=general source=liccon_general",
            ):
                total_chunks += 1
        print(
            "LICCON general: added "
            f"{len(liccon_chunks)} chunks from output/general/liccon_general_starterpack.json"
        )

    # --- NEW ---
    index_version_path = BASE_DIR / "output" / "embeddings" / "index_version.json"
    git_commit = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            git_commit = (result.stdout or "").strip() or "unknown"
    except Exception:
        git_commit = "unknown"

    index_version = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit,
        "chunks_total": WRITTEN_CHUNKS,
        "chunks_by_layer": CHUNKS_BY_LAYER,
        "source_files": SOURCE_FILES,
    }
    index_version_path.parent.mkdir(parents=True, exist_ok=True)
    with index_version_path.open("w", encoding="utf-8") as f:
        json.dump(index_version, f, ensure_ascii=False, indent=2)

    print(f"\n[RESULT] Gesamt-Chunks: {total_chunks}")
    print(f"[RESULT] JSONL geschrieben nach: {OUT_CHUNKS}")
    print(f"DEDUP: skipped {DEDUPE_SKIPPED} duplicate chunks by hash")
    print(f"VALIDATION: unique ids OK ({len(META_ID_SOURCES)} total)")
    print(f"VERSION: wrote {index_version_path}")
    print("=== FERTIG ===")


# Alias für alte Webapp-Imports
def export_chunks_jsonl() -> None:
    export()


if __name__ == "__main__":
    export()

# Run:
# 1) python scripts/export_for_embeddings.py
# 2) python scripts/build_local_embedding_index.py
