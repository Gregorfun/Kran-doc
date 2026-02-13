"""
Quick Test Script for Semantic Search API
==========================================

Tests /api/status and /api/search with API key authentication.
"""

import json
import sys
import urllib.error
import urllib.request

API_KEY = "test-semantic-key"
BASE_URL = "http://127.0.0.1:5002"


def test_status():
    """Test /api/status endpoint"""
    print("\n=== Testing /api/status ===")
    req = urllib.request.Request(f"{BASE_URL}/api/status", headers={"X-API-Key": API_KEY}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"✅ Status code: {r.status}")
            body = r.read().decode("utf-8")
            data = json.loads(body)
            print(f"✅ Embedding available: {data.get('status', {}).get('embedding_index_available', 'unknown')}")
            return True
    except urllib.error.URLError as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_search(query="Fehlercode E01"):
    """Test /api/search endpoint"""
    print(f"\n=== Testing /api/search query='{query}' ===")

    # URL encode query parameters
    params = urllib.parse.urlencode({"q": query, "limit": 3})
    url = f"{BASE_URL}/api/search?{params}"

    req = urllib.request.Request(url, headers={"X-API-Key": API_KEY}, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"✅ Status code: {r.status}")
            body = r.read().decode("utf-8")
            data = json.loads(body)

            results = data.get("results", [])
            print(f"✅ Found {len(results)} results")

            for i, res in enumerate(results):
                print(f"  {i+1}. [{res.get('score', 0):.2f}] {res.get('filename')} (Page {res.get('page')})")

            return True

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.read().decode('utf-8')}")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Connection error: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Starting Semantic API Tests...")

    if test_status():
        test_search("LTC 1050")
        test_search("Fehlercode E92")
    else:
        print("⚠️  Skipping search tests because status check failed.")
        sys.exit(1)
