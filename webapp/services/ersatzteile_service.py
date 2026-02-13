from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_ersatzteile_request(data: Dict[str, Any]) -> Dict[str, Any]:
    model = data.get("model") or None
    query = (data.get("query") or "").strip()
    try:
        limit = int(data.get("limit") or 10)
    except Exception:
        limit = 10
    limit = max(1, min(limit, 200))
    return {
        "model": model,
        "query": query,
        "limit": limit,
    }


def validate_ersatzteile_request(*, model: Optional[str], query: str) -> Optional[str]:
    if not model:
        return "Bitte ein Modell auswählen"
    if not query:
        return "Bitte Suchbegriff eingeben."
    return None


def load_ersatzteile_for_model(*, models_dir: str, model: str) -> Optional[Dict[str, Any]]:
    path = Path(models_dir) / model / "ersatzteile.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def search_ersatzteile(*, data: Dict[str, Any], model: str, query: str, limit: int) -> List[Dict[str, Any]]:
    query_lower = (query or "").lower()
    if not query_lower:
        return []

    def matches(value: Any) -> bool:
        if value is None:
            return False
        return query_lower in str(value).lower()

    results: List[Dict[str, Any]] = []
    remaining = max(1, min(int(limit or 10), 200))

    for assembly in data.get("assemblies") or []:
        if remaining <= 0:
            break
        if not isinstance(assembly, dict):
            continue

        assembly_match = any(matches(assembly.get(key)) for key in ("name_de", "name_en", "assembly_article"))

        selected_parts: List[Dict[str, Any]] = []
        for part in assembly.get("parts") or []:
            if remaining <= 0:
                break
            if not isinstance(part, dict):
                continue
            part_match = assembly_match or any(
                matches(part.get(key))
                for key in (
                    "article_no",
                    "article",
                    "name_de",
                    "name_en",
                    "designation_de",
                    "designation_en",
                    "bezeichnung_de",
                    "description_en",
                    "bezeichnung",
                    "text",
                    "pos",
                )
            )
            if not part_match:
                continue

            article_no = part.get("article_no") or part.get("article")
            name_de = (
                part.get("name_de")
                or part.get("designation_de")
                or part.get("bezeichnung_de")
                or part.get("bezeichnung")
                or part.get("text")
            )
            name_en = part.get("name_en") or part.get("designation_en") or part.get("description_en")

            selected_parts.append(
                {
                    "pos": part.get("pos"),
                    "article_no": article_no,
                    "qty": part.get("qty"),
                    "name_de": name_de,
                    "name_en": name_en,
                    "model": model,
                    "source_type": "etk_part",
                }
            )
            remaining -= 1

        if not selected_parts:
            continue

        results.append(
            {
                "assembly_article": assembly.get("assembly_article"),
                "name_de": assembly.get("name_de"),
                "name_en": assembly.get("name_en"),
                "ref_page": assembly.get("ref_page"),
                "parts": selected_parts,
            }
        )

    return results
