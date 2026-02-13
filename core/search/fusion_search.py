"""
Fusion Search Service
=====================

Kombiniert Exact, Fuzzy und Semantic Search mit Ranking
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz, process

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


@dataclass
class SearchResult:
    """Single search result"""

    id: str
    collection: str
    score: float
    content: str
    metadata: Dict[str, Any]
    source_document: Optional[str] = None
    page_number: Optional[int] = None
    confidence: Optional[float] = None
    bbox: Optional[Dict[str, float]] = None
    match_type: str = "semantic"  # exact, fuzzy, semantic


class FusionSearchService:
    """
    Fusion Search kombiniert:
    - Exact: Regex für LEC-\\d+, BMK Codes, Klemmen
    - Fuzzy: RapidFuzz für Tippfehler
    - Semantic: Vektor-Suche via Qdrant
    """

    def __init__(self, qdrant_client=None, collection_name: str = "kran_doc"):
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

        # Regex patterns for exact matching
        self.patterns = {
            "lec": re.compile(r"\bLEC-?\d{4,5}\b", re.IGNORECASE),
            "bmk": re.compile(r"\b[A-Z]\d{1,3}(?:-[A-Z]\d{1,2})?\b"),
            "klemme": re.compile(r"\b[XYZ]\d{1,3}:\d{1,3}\b", re.IGNORECASE),
            "address": re.compile(r"\b[SY]\d{3,4}\b"),
        }

    def search(
        self,
        query: str,
        mode: str = "auto",
        limit: int = 20,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Main search entry point

        Args:
            query: Search query
            mode: auto|exact|fuzzy|semantic
            limit: Max results
            threshold: Minimum score threshold
            filters: Additional filters (model, type, etc.)

        Returns:
            List of SearchResult objects ranked by score
        """

        if mode == "exact":
            return self._exact_search(query, limit, filters)
        elif mode == "fuzzy":
            return self._fuzzy_search(query, limit, threshold, filters)
        elif mode == "semantic":
            return self._semantic_search(query, limit, threshold, filters)
        else:  # auto = fusion
            return self._fusion_search(query, limit, threshold, filters)

    def _exact_search(self, query: str, limit: int, filters: Optional[Dict[str, Any]]) -> List[SearchResult]:
        """Exact pattern matching"""
        results = []

        # Check all patterns
        for pattern_name, pattern in self.patterns.items():
            matches = pattern.findall(query)
            if matches:
                # Search in Qdrant with exact filter
                for match in matches:
                    results.extend(self._search_by_code(match, pattern_name, filters))

        # Deduplicate and sort by score
        seen = set()
        unique_results = []
        for r in sorted(results, key=lambda x: x.score, reverse=True):
            key = (r.collection, r.id)
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        return unique_results[:limit]

    def _fuzzy_search(
        self, query: str, limit: int, threshold: float, filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Fuzzy string matching"""
        if not RAPIDFUZZ_AVAILABLE:
            # Fallback to exact
            return self._exact_search(query, limit, filters)

        results = []

        # Get all codes from index (would need to be cached)
        # For now, do fuzzy matching on retrieved results

        # First get semantic results
        semantic = self._semantic_search(query, limit * 2, threshold * 0.8, filters)

        # Apply fuzzy matching on codes/titles
        for result in semantic:
            code = result.metadata.get("code") or result.metadata.get("bmk_code") or ""
            title = result.metadata.get("title") or result.metadata.get("name") or ""

            # Fuzzy match on code
            if code:
                code_score = fuzz.ratio(query.upper(), code.upper()) / 100.0
                if code_score > threshold:
                    result.score = max(result.score, code_score * 0.9)  # Boost
                    result.match_type = "fuzzy"
                    results.append(result)

            # Fuzzy match on title
            if title:
                title_score = fuzz.partial_ratio(query.lower(), title.lower()) / 100.0
                if title_score > threshold:
                    result.score = max(result.score, title_score * 0.8)
                    if result not in results:
                        result.match_type = "fuzzy"
                        results.append(result)

        return sorted(results, key=lambda x: x.score, reverse=True)[:limit]

    def _semantic_search(
        self, query: str, limit: int, threshold: float, filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Semantic vector search via Qdrant"""
        if not self.qdrant_client:
            return []

        try:
            # Generate query embedding
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            query_vector = model.encode(query).tolist()

            # Build Qdrant filter
            qdrant_filter = None
            if filters:
                qdrant_filter = self._build_qdrant_filter(filters)

            # Search
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=threshold,
                query_filter=qdrant_filter,
            )

            results = []
            for hit in search_results:
                payload = hit.payload or {}
                results.append(
                    SearchResult(
                        id=str(hit.id),
                        collection=self.collection_name,
                        score=hit.score,
                        content=payload.get("text", ""),
                        metadata=payload,
                        source_document=payload.get("source_document"),
                        page_number=payload.get("page_number"),
                        confidence=payload.get("confidence"),
                        bbox=payload.get("bbox"),
                        match_type="semantic",
                    )
                )

            return results

        except Exception as e:
            print(f"Semantic search error: {e}")
            return []

    def _fusion_search(
        self, query: str, limit: int, threshold: float, filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Fusion: Combine exact, fuzzy, semantic with ranking

        Scoring:
        - Exact match: 1.0 score boost
        - Fuzzy match: 0.5-0.9 boost based on similarity
        - Semantic: base score from vector similarity
        """

        all_results = []

        # 1. Exact search
        exact_results = self._exact_search(query, limit, filters)
        for r in exact_results:
            r.score = 1.0  # Maximum boost for exact
            r.match_type = "exact"
            all_results.append(r)

        # 2. Semantic search
        semantic_results = self._semantic_search(query, limit * 2, threshold * 0.8, filters)
        all_results.extend(semantic_results)

        # 3. Fuzzy search (on semantic results)
        if RAPIDFUZZ_AVAILABLE:
            for r in semantic_results:
                code = r.metadata.get("code") or r.metadata.get("bmk_code") or ""
                if code:
                    code_score = fuzz.ratio(query.upper(), code.upper()) / 100.0
                    if code_score > 0.7:
                        r.score = r.score * 0.5 + code_score * 0.5  # Blend scores
                        r.match_type = "fuzzy"

        # Deduplicate by (collection, id)
        seen = {}
        for r in all_results:
            key = (r.collection, r.id)
            if key not in seen or r.score > seen[key].score:
                seen[key] = r

        # Sort by score
        final_results = sorted(seen.values(), key=lambda x: x.score, reverse=True)

        return final_results[:limit]

    def _search_by_code(self, code: str, pattern_type: str, filters: Optional[Dict[str, Any]]) -> List[SearchResult]:
        """Search for exact code in Qdrant"""
        if not self.qdrant_client:
            return []

        try:
            # Build filter for exact code match
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            field_name = "code" if pattern_type == "lec" else "bmk_code"

            scroll_filter = Filter(must=[FieldCondition(key=field_name, match=MatchValue(value=code.upper()))])

            # Add additional filters
            if filters:
                # Extend filter (simplified)
                pass

            # Scroll to get all matching
            results = []
            offset = None
            while True:
                response = self.qdrant_client.scroll(
                    collection_name=self.collection_name, scroll_filter=scroll_filter, limit=100, offset=offset
                )

                points, offset = response

                for point in points:
                    payload = point.payload or {}
                    results.append(
                        SearchResult(
                            id=str(point.id),
                            collection=self.collection_name,
                            score=1.0,  # Exact match
                            content=payload.get("text", ""),
                            metadata=payload,
                            source_document=payload.get("source_document"),
                            page_number=payload.get("page_number"),
                            confidence=payload.get("confidence"),
                            bbox=payload.get("bbox"),
                            match_type="exact",
                        )
                    )

                if offset is None:
                    break

            return results

        except Exception as e:
            print(f"Code search error: {e}")
            return []

    def _build_qdrant_filter(self, filters: Dict[str, Any]):
        """Build Qdrant filter from dict"""
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            conditions = []

            if "model" in filters:
                conditions.append(FieldCondition(key="model_series", match=MatchValue(value=filters["model"])))

            if "type" in filters:
                conditions.append(FieldCondition(key="source_type", match=MatchValue(value=filters["type"])))

            if conditions:
                return Filter(must=conditions)

        except Exception:
            pass

        return None
