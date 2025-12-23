# parsers/ersatzteile_parser.py
from __future__ import annotations

import re
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pypdf import PdfReader


# ----------------------------
# Datenmodelle
# ----------------------------

@dataclass
class SparePartRow:
    pos: str                      # "1" oder "(880)" etc.
    article_no: str               # Artikelnummer
    qty: str                      # Menge (manchmal "0.232" etc.)
    name_de: str                  # Bezeichnung DE
    name_en: str                  # Description EN (kann leer sein)

@dataclass
class Assembly:
    name_de: str
    name_en: str
    assembly_article: str         # z.B. "918414708"
    ref_page: Optional[int]       # Seite aus Übersicht (falls gefunden)
    parts: List[SparePartRow]

@dataclass
class SparePartsDoc:
    model: str
    source_pdf: str
    created_at: str
    assemblies: List[Assembly]


# ----------------------------
# Regex / Heuristiken
# ----------------------------

# Kopfzeile einer Teileliste-Seite erkennen
RE_TABLE_HEADER = re.compile(r"^\s*Pos\.\s+Artikel\s+Menge\s+Bezeichnung\s+Description\s*$", re.MULTILINE)

# Zeile in Übersicht (Inhalts-/Gruppenliste) erkennen:
# Beispiel (aus PDF): "3 918414708 1 KUEHLER EINBAU COOLER INSTALLATION ➩ ❏ 13"
RE_TOC_LINE = re.compile(
    r"^\s*(\d+)\s+(\d{6,12})\s+(\d+)\s+(.+?)\s{2,}(.+?)(?:\s+➩\s+❏\s+(\d+))?\s*$"
)

# Teilelisten-Zeile erkennen:
# Beispiel: "1 96011958 1 KUEHLER VORM. RADIATOR, PRE-ASSEMBLED ➩ ❏ 15"
# oder Unterpos: "(880) 97092342 1 ROHR GEBOGEN ... TUBE BENT"
RE_PART_LINE = re.compile(
    r"^\s*(\(\d+\)|\d+)\s+(\d{6,12})\s+([0-9]+(?:[.,][0-9]+)?)\s+(.+?)(?:\s{2,}(.+?))?\s*$"
)

# Titelblock einer Gruppe (oberhalb der Tabelle) – sehr locker:
# typischerweise: "KUEHLER EINBAU" / "COOLER INSTALLATION 918414708"
RE_GROUP_TITLE = re.compile(
    r"^\s*([A-Z0-9ÄÖÜß\-\.\,\/\(\)\s]{6,})\s*$", re.MULTILINE
)

RE_MODEL = re.compile(r"\bLTM\s*\d{3,4}[-/]\d(?:\.\d)?\b|\bLTM\s*\d{3,4}[-/]\d\.\d\b|\bLTM\s*\d{3,4}[-/]\d(?:-\d)?(?:\.\d)?\b")


# ----------------------------
# Helpers
# ----------------------------

def _clean(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _extract_text(reader: PdfReader, i: int) -> str:
    try:
        txt = reader.pages[i].extract_text() or ""
        return txt
    except Exception:
        return ""

def _split_combined_designation(text: str) -> Tuple[str, str]:
    """
    Conservative split: if a DE abbreviation ends with ". " and a clear EN keyword follows.
    Otherwise keep everything as DE.
    """
    s = _clean(text)
    if not s:
        return "", ""

    en_keywords = [
        "INJECTOR", "SEAL", "KIT", "WITH", "WITHOUT", "FOR", "ASSY", "ASSEMBLY",
        "COMPLETE", "CYLINDER", "PUMP", "VALVE", "HOSE", "BOLT", "NUT", "SCREW",
        "RING", "SENSOR"
    ]
    en_re = re.compile(r"\b(" + "|".join(en_keywords) + r")\b")

    dot_matches = [m.start() for m in re.finditer(r"\.\s+", s)]
    for cut in reversed(dot_matches):
        left = s[:cut + 1].strip()
        right = s[cut + 1:].strip()
        if left and right and en_re.search(right):
            return left, right

    return s, ""


# ----------------------------
# Parser Kern
# ----------------------------

def detect_model(reader: PdfReader, scan_pages: int = 10) -> str:
    """
    Scannt die ersten Seiten nach dem Modell-String (z.B. LTM 1090-4.2).
    In deinem PDF taucht das Modell schon sehr früh auf. :contentReference[oaicite:1]{index=1}
    """
    best = ""
    for i in range(min(scan_pages, len(reader.pages))):
        t = _extract_text(reader, i)
        m = RE_MODEL.search(t)
        if m:
            best = _clean(m.group(0))
            break
    return best or "UNKNOWN_MODEL"

def parse_toc(reader: PdfReader, start_page: int = 7, end_page: int = 12) -> List[Tuple[str, str, str, Optional[int]]]:
    """
    Liest die Übersicht/TOC-Seiten und extrahiert Gruppen:
    returns: (name_de, name_en, assembly_article, ref_page)
    Die Übersicht mit Pos/Artikel/Menge/Bezeichnung/Description ist im PDF sichtbar (z.B. Seite 8ff). :contentReference[oaicite:2]{index=2}
    """
    groups: List[Tuple[str, str, str, Optional[int]]] = []

    # PDF-Seiten sind 0-based; die sichtbare "8 (8/12)" entspricht oft reader index 7
    for idx in range(start_page, min(end_page, len(reader.pages))):
        text = _extract_text(reader, idx)
        if not text:
            continue

        lines = [l.rstrip() for l in text.splitlines() if l.strip()]
        for line in lines:
            m = RE_TOC_LINE.match(line)
            if not m:
                continue
            _pos, art, _qty, de, en, ref = m.groups()
            groups.append((_clean(de), _clean(en), _clean(art), int(ref) if ref else None))

    # Dedupe (manchmal doppelt)
    seen = set()
    out = []
    for de, en, art, ref in groups:
        key = (de, en, art, ref)
        if key in seen:
            continue
        seen.add(key)
        out.append((de, en, art, ref))
    return out

def parse_parts_page(text: str) -> Tuple[Optional[str], Optional[str], List[SparePartRow]]:
    """
    Parst eine einzelne Seite: versucht Gruppentitel (DE/EN) + Teilezeilen.
    """
    if not text:
        return None, None, []

    # Nur Seiten mit Tabellenkopf anfassen
    if not RE_TABLE_HEADER.search(text):
        return None, None, []

    lines = [l.rstrip() for l in text.splitlines()]

    # 1) Gruppentitel heuristisch: wir nehmen die Zeilen VOR "Pos. Artikel Menge..."
    header_idx = None
    for i, l in enumerate(lines):
        if "Pos." in l and "Artikel" in l and "Menge" in l:
            header_idx = i
            break

    title_block = "\n".join(lines[:header_idx]) if header_idx is not None else ""
    # Titelblock enthält meist:
    # DE Titel in Caps + EN Titel + Artikelnummer
    # Beispiel in PDF: "KUEHLER EINBAU" / "COOLER INSTALLATION 918414708" :contentReference[oaicite:3]{index=3}
    tb_lines = [_clean(x) for x in title_block.splitlines() if _clean(x)]

    # Sehr einfache Heuristik:
    # - erste "caps" Zeile als DE
    # - nächste (nicht-caps) / englische als EN, oder wir lassen EN leer
    name_de = None
    name_en = None

    # Suche nach zwei Titelzeilen am Stück
    candidates = [x for x in tb_lines if len(x) >= 6 and not x.startswith("etk_") and "LIEBHERR" not in x]
    if candidates:
        # Häufig ist die DE Zeile komplett groß
        name_de = candidates[0]
        if len(candidates) >= 2:
            # zweite Zeile kann EN + Artikelnummer enthalten -> Artikelnummer am Ende entfernen
            en_line = candidates[1]
            en_line = re.sub(r"\b\d{6,12}\b$", "", en_line).strip()
            name_en = en_line or None

    # 2) Teilezeilen parsen
    parts: List[SparePartRow] = []
    for l in lines:
        m = RE_PART_LINE.match(l)
        if not m:
            continue
        pos, article, qty, de, en = m.groups()
        name_de = _clean(de)
        name_en = _clean(en or "")
        if not name_en:
            name_de, name_en = _split_combined_designation(name_de)
        parts.append(
            SparePartRow(
                pos=_clean(pos),
                article_no=_clean(article),
                qty=_clean(qty),
                name_de=name_de,
                name_en=name_en,
            )
        )

    return name_de, name_en, parts

def parse_spare_parts_pdf(pdf_path: str | Path) -> SparePartsDoc:
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))

    model = detect_model(reader)
    toc_groups = parse_toc(reader)

    # Assemblies vorbereiten
    assemblies: Dict[str, Assembly] = {}
    for de, en, art, ref_page in toc_groups:
        assemblies[art] = Assembly(
            name_de=de,
            name_en=en,
            assembly_article=art,
            ref_page=ref_page,
            parts=[],
        )

    # Teilelisten im gesamten PDF suchen (brute-force, aber robust)
    # Optimierung später: über ref_page springen.
    for i in range(len(reader.pages)):
        text = _extract_text(reader, i)
        name_de, name_en, parts = parse_parts_page(text)
        if not parts:
            continue

        # Versuch: die Seite gehört zu welcher Assembly?
        # Oft steht im Titelblock die Assembly-Artikelnummer oder in Fußzeile.
        # Wir suchen nach einer 6-12 stelligen Zahl, die mit assemblies matcht.
        match_art = None
        for art in list(assemblies.keys()):
            if art in text:
                match_art = art
                break

        if match_art is None:
            # fallback: wenn wir noch keine assemblies haben, legen wir "UNKNOWN" an
            match_art = "UNKNOWN"

        if match_art not in assemblies:
            assemblies[match_art] = Assembly(
                name_de=name_de or "UNKNOWN",
                name_en=name_en or "",
                assembly_article=match_art,
                ref_page=None,
                parts=[],
            )

        # Titel ergänzen, falls leer
        if name_de and assemblies[match_art].name_de in ("", "UNKNOWN"):
            assemblies[match_art].name_de = name_de
        if name_en and not assemblies[match_art].name_en:
            assemblies[match_art].name_en = name_en

        assemblies[match_art].parts.extend(parts)

    doc = SparePartsDoc(
        model=model,
        source_pdf=str(pdf_path.name),
        created_at=datetime.utcnow().isoformat() + "Z",
        assemblies=[a for a in assemblies.values() if a.parts],  # nur Assemblies mit Inhalt
    )
    return doc

def save_spare_parts_json(doc: SparePartsDoc, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _part_payload(p: SparePartRow) -> Dict[str, str]:
        return {
            "pos": p.pos,
            "article_no": p.article_no,
            "qty": p.qty,
            "name_de": p.name_de,
            "name_en": p.name_en,
        }

    payload = {
        "model": doc.model,
        "source_pdf": doc.source_pdf,
        "created_at": doc.created_at,
        "assemblies": [
            {
                "name_de": a.name_de,
                "name_en": a.name_en,
                "assembly_article": a.assembly_article,
                "ref_page": a.ref_page,
                "parts": [_part_payload(p) for p in a.parts],
            }
            for a in doc.assemblies
        ],
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def merge_spare_parts_docs(docs: List[SparePartsDoc], model: str) -> SparePartsDoc:
    assemblies: Dict[str, Assembly] = {}
    part_keys: Dict[str, set[Tuple[str, str, str, str, str]]] = {}

    for doc in docs:
        for a in doc.assemblies:
            if a.assembly_article not in assemblies:
                assemblies[a.assembly_article] = Assembly(
                    name_de=a.name_de,
                    name_en=a.name_en,
                    assembly_article=a.assembly_article,
                    ref_page=a.ref_page,
                    parts=[],
                )
                part_keys[a.assembly_article] = set()

            merged = assemblies[a.assembly_article]

            if a.name_de and merged.name_de in ("", "UNKNOWN"):
                merged.name_de = a.name_de
            if a.name_en and not merged.name_en:
                merged.name_en = a.name_en
            if a.ref_page is not None and merged.ref_page is None:
                merged.ref_page = a.ref_page

            keys = part_keys[a.assembly_article]
            for p in a.parts:
                key = (p.pos, p.article_no, p.qty, p.name_de, p.name_en)
                if key in keys:
                    continue
                keys.add(key)
                merged.parts.append(p)

    return SparePartsDoc(
        model=model,
        source_pdf="MULTI",
        created_at=datetime.utcnow().isoformat() + "Z",
        assemblies=[a for a in assemblies.values() if a.parts],
    )


# ----------------------------
# CLI
# ----------------------------

def main():
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Parse Liebherr spare parts catalogue PDF into JSON.")
    ap.add_argument("model", help="Model name (e.g. LTM1090-4.2)")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    etk_dir = project_root / "input" / args.model / "etk"
    if not etk_dir.exists():
        print("[ERROR] etk_dir not found:", etk_dir)
        sys.exit(1)

    pdf_paths = sorted(etk_dir.glob("*.pdf"))
    if not pdf_paths:
        print("[ERROR] No PDFs found in:", etk_dir)
        sys.exit(1)

    docs: List[SparePartsDoc] = []
    for pdf in pdf_paths:
        print("[INFO] Parsing:", pdf.name)
        doc = parse_spare_parts_pdf(pdf)
        if doc.model != "UNKNOWN_MODEL" and doc.model != args.model:
            print("[WARN] Detected model", doc.model, "in", pdf.name, "!= requested", args.model)
        docs.append(doc)

    merged = merge_spare_parts_docs(docs, args.model)
    out_path = project_root / "output" / "models" / args.model / "ersatzteile.json"
    out = save_spare_parts_json(merged, out_path)
    print("[OK] PDFs:", len(pdf_paths), "Assemblies:", len(merged.assemblies), "Output:", out)

if __name__ == "__main__":
    main()
