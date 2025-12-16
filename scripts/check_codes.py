from pathlib import Path
import json

# Pfad zur Embedding-Chunks-Datei
path = Path("output/embeddings/knowledge_chunks.jsonl")

if not path.exists():
    print(f"Datei nicht gefunden: {path.resolve()}")
    raise SystemExit(1)

count_1A0350 = 0
count_319502 = 0
examples_1A0350 = []
examples_319502 = []

with path.open("r", encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)
        meta = obj.get("metadata", {}) or {}
        code = str(meta.get("code", "")).strip().upper().replace(" ", "")

        if code == "1A0350":
            count_1A0350 += 1
            if len(examples_1A0350) < 2:
                examples_1A0350.append(obj)

        if code == "319502":
            count_319502 += 1
            if len(examples_319502) < 2:
                examples_319502.append(obj)

print(f"Anzahl Chunks mit code=1A0350: {count_1A0350}")
print(f"Anzahl Chunks mit code=319502: {count_319502}")

if examples_1A0350:
    print("\n=== Beispiel-Chunks für 1A0350 ===")
    for ex in examples_1A0350:
        print(json.dumps(ex, ensure_ascii=False, indent=2))

if examples_319502:
    print("\n=== Beispiel-Chunks für 319502 ===")
    for ex in examples_319502:
        print(json.dumps(ex, ensure_ascii=False, indent=2))
