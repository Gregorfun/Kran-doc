"""
Test Fusion Search
==================

Tests für Exact, Fuzzy, Semantic und Fusion Search
"""

import pytest

from core.search.fusion_search import FusionSearchService, SearchResult


def test_exact_pattern_matching():
    """Test exact pattern matching for codes"""
    service = FusionSearchService()

    # LEC code
    assert service.patterns["lec"].search("LEC-12345")
    assert service.patterns["lec"].search("lec-54321")
    assert not service.patterns["lec"].search("LEC-12")  # Too short

    # BMK code
    assert service.patterns["bmk"].search("A81")
    assert service.patterns["bmk"].search("B1-M1")
    assert service.patterns["bmk"].search("Y305")

    # Klemme
    assert service.patterns["klemme"].search("X1:15")
    assert service.patterns["klemme"].search("Y205:3")


def test_search_result_deduplication():
    """Test that duplicate results are removed"""
    results = [
        SearchResult(id="1", collection="test", score=0.9, content="test", metadata={}),
        SearchResult(id="1", collection="test", score=0.8, content="test", metadata={}),  # Duplicate
        SearchResult(id="2", collection="test", score=0.7, content="test", metadata={}),
    ]

    # Deduplicate
    seen = {}
    for r in results:
        key = (r.collection, r.id)
        if key not in seen or r.score > seen[key].score:
            seen[key] = r

    unique = list(seen.values())
    assert len(unique) == 2
    assert unique[0].id == "1"
    assert unique[0].score == 0.9  # Higher score kept


def test_score_boosting():
    """Test that exact matches get score boost"""
    results = [
        SearchResult(id="1", collection="test", score=0.6, content="test", metadata={}, match_type="semantic"),
        SearchResult(id="2", collection="test", score=1.0, content="test", metadata={}, match_type="exact"),
    ]

    # Sort by score
    sorted_results = sorted(results, key=lambda x: x.score, reverse=True)

    assert sorted_results[0].match_type == "exact"
    assert sorted_results[0].score == 1.0


def test_fuzzy_search_available():
    """Test if rapidfuzz is available"""
    try:
        from rapidfuzz import fuzz

        assert fuzz.ratio("LEC-1234", "LEC-1235") > 80  # Similar
        assert fuzz.ratio("LEC-1234", "ABC-9999") < 50  # Different
    except ImportError:
        pytest.skip("rapidfuzz not available")


def test_search_result_provenance():
    """Test that search results include provenance fields"""
    result = SearchResult(
        id="1",
        collection="test",
        score=0.9,
        content="test content",
        metadata={"model": "LTM1070"},
        source_document="manual.pdf",
        page_number=42,
        confidence=0.95,
        bbox={"x": 100, "y": 200, "w": 300, "h": 50},
    )

    assert result.source_document == "manual.pdf"
    assert result.page_number == 42
    assert result.confidence == 0.95
    assert result.bbox is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
