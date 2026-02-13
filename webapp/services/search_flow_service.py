from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def run_search_flow(
    *,
    data: Dict[str, Any],
    search_similar: Callable[..., List[Dict[str, Any]]] | None,
    extract_error_codes: Callable[[str], List[str]],
    is_pure_code_query: Callable[[str, List[str], Optional[str]], bool],
    direct_lec_results_for_codes: Callable[[List[str], Optional[str], int], List[Dict[str, Any]]],
    enrich_results_with_bmk: Callable[[List[Dict[str, Any]], Optional[str]], List[Dict[str, Any]]],
    search_general: Callable[[str, int], List[Dict[str, Any]]],
    enrich_primary_results: Callable[[List[Dict[str, Any]], str], List[Dict[str, Any]]],
    enrich_general_results: Callable[[List[Dict[str, Any]], str], List[Dict[str, Any]]],
    logger: Any,
) -> Dict[str, Any]:
    if search_similar is None:
        return {"ok": False, "error": "Embedding-Suche nicht verfügbar (semantic_index fehlt)", "status": 500}

    question = (data.get("question") or "").strip()
    top_k = int(data.get("top_k") or 5)
    model = (data.get("model") or "").strip()
    if model.lower() in ("alle", "all", "*"):
        model = ""

    source_type = (data.get("source_type") or "").strip()
    source_type_filter = source_type
    if not source_type_filter or source_type_filter.lower() in ("alle", "all", "*"):
        source_type_filter = None
    source_mode = (source_type_filter or "general").lower()

    if not question:
        return {"ok": False, "error": "Bitte eine Frage eingeben.", "status": 400}
    if not model:
        return {"ok": False, "error": "Bitte ein Modell auswählen", "status": 400}

    requested_codes = extract_error_codes(question)
    if source_mode in ("lec_error", "combo") and is_pure_code_query(question, requested_codes, "lec_error"):
        results = direct_lec_results_for_codes(requested_codes, model, 1)
        results = enrich_results_with_bmk(results, model)
        results = enrich_primary_results(results, model)

        general_results: List[Dict[str, Any]] = []
        if source_mode == "combo":
            general_results = search_general(question, top_k)
            logger.debug("[GENERAL] returned %s items", len(general_results))
            general_results = enrich_general_results(general_results, model)

        logger.info(
            "[SEARCH] q=%r model=%r source_type_filter=%r results=%s general=%s",
            question,
            model,
            source_mode,
            len(results),
            len(general_results),
        )
        return {"ok": True, "results": results, "general_results": general_results}

    try:
        if source_mode == "general":
            results = []
            general_results = search_general(question, top_k)
        elif source_mode == "combo":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="lec_error")
            general_results = search_general(question, top_k)
        elif source_mode == "lec_error":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="lec_error")
            general_results = []
        elif source_mode == "spl":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="spl")
            general_results = []
        elif source_mode == "manual":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="manual")
            general_results = []
        else:
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter=source_type_filter)
            general_results = []
    except TypeError:
        results = search_similar(question, top_k)
        general_results = []
    except Exception as error:
        return {"ok": False, "error": f"Fehler bei der Embedding-Suche: {error}", "status": 500}

    if results:
        results = enrich_results_with_bmk(results, model)
        results = enrich_primary_results(results, model)

    if general_results:
        logger.debug("[GENERAL] returned %s items", len(general_results))
        general_results = enrich_general_results(general_results, model)

    logger.info(
        "[SEARCH] q=%r model=%r source_type_filter=%r results=%s general=%s",
        question,
        model,
        source_mode,
        len(results),
        len(general_results),
    )

    return {"ok": True, "results": results, "general_results": general_results}
