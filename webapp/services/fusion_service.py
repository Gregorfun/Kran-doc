from __future__ import annotations

from typing import Any, Dict, List


def parse_fusion_request_data(*, method: str, args: Any, json_data: Dict[str, Any]) -> Dict[str, Any]:
    if method == "POST":
        query = json_data.get("q") or json_data.get("query", "")
        mode = json_data.get("mode", "auto")
        limit = int(json_data.get("limit", 20))
        filters = json_data.get("filters")
    else:
        query = args.get("q") or args.get("query", "")
        mode = args.get("mode", "auto")
        limit = int(args.get("limit", 20))
        filters = None

    return {
        "query": query,
        "mode": mode,
        "limit": limit,
        "filters": filters,
    }


def format_fusion_results(*, query: str, mode: str, results: List[Any]) -> Dict[str, Any]:
    return {
        "query": query,
        "mode": mode,
        "total": len(results),
        "results": [
            {
                "id": result.id,
                "score": result.score,
                "match_type": result.match_type,
                "content": result.content[:500],
                "source_document": result.source_document,
                "page_number": result.page_number,
                "confidence": result.confidence,
                "metadata": result.metadata,
            }
            for result in results
        ],
    }
