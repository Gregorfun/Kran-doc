"""
Qdrant Vector Database Integration für Kran-Doc
================================================

Verwaltet semantische Suche mit Qdrant:
- Collections für verschiedene Dokumenttypen
- Embedding-Generierung
- Semantische Queries

Author: Gregor
Version: 2.0
"""

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        SearchParams,
        VectorParams,
    )

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("Qdrant nicht installiert: pip install qdrant-client")

try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("Sentence-Transformers nicht installiert")


@dataclass
class QdrantConfig:
    """Konfiguration für Qdrant"""

    # Connection
    host: str = "localhost"
    port: int = 6333
    path: Optional[str] = "./data/qdrant"  # Für lokalen Mode
    use_local: bool = True  # True = Datei-basiert, False = Server

    # Embedding Model
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    embedding_dimension: int = 768

    # Collections
    collections: List[str] = None

    def __post_init__(self):
        if self.collections is None:
            self.collections = ["lec_errors", "bmk_components", "spl_circuits", "manuals_chunks", "community_solutions"]


class QdrantVectorDB:
    """
    Qdrant Vector Database Manager

    Beispiel:
        db = QdrantVectorDB()
        db.init_collections()
        db.add_documents("lec_errors", documents)
        results = db.search("lec_errors", "Hydraulikfehler")
    """

    def __init__(self, config: Optional[QdrantConfig] = None):
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant nicht installiert: pip install qdrant-client")

        self.config = config or QdrantConfig()
        self.client = self._init_client()
        self.embedder = self._init_embedder()

        logger.info("QdrantVectorDB initialisiert")

    def _init_client(self) -> QdrantClient:
        """Initialisiert Qdrant Client"""
        if self.config.use_local:
            # Lokaler Datei-Modus (kein Server nötig)
            logger.info(f"Verwende lokalen Qdrant-Speicher: {self.config.path}")
            Path(self.config.path).mkdir(parents=True, exist_ok=True)
            return QdrantClient(path=self.config.path)
        else:
            # Server-Modus
            logger.info(f"Verbinde zu Qdrant-Server: {self.config.host}:{self.config.port}")
            return QdrantClient(host=self.config.host, port=self.config.port)

    def _init_embedder(self):
        """Initialisiert Embedding-Modell"""
        if not EMBEDDINGS_AVAILABLE:
            logger.warning("Sentence-Transformers nicht verfügbar")
            return None

        logger.info(f"Lade Embedding-Modell: {self.config.embedding_model}")
        return SentenceTransformer(self.config.embedding_model)

    def init_collections(self, force: bool = False):
        """
        Initialisiert alle Collections

        Args:
            force: Wenn True, löscht existierende Collections
        """
        for collection_name in self.config.collections:
            self.create_collection(collection_name, force=force)

    def create_collection(self, name: str, force: bool = False):
        """
        Erstellt eine Collection

        Args:
            name: Collection-Name
            force: Löscht existierende Collection
        """
        try:
            # Prüfe ob Collection existiert
            exists = self.client.collection_exists(name)

            if exists and force:
                logger.info(f"Lösche existierende Collection: {name}")
                self.client.delete_collection(name)
                exists = False

            if not exists:
                logger.info(f"Erstelle Collection: {name}")
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=self.config.embedding_dimension, distance=Distance.COSINE),
                )
            else:
                logger.info(f"Collection existiert bereits: {name}")

        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Collection {name}: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generiert Embedding für Text

        Args:
            text: Input-Text

        Returns:
            Vektor als Liste
        """
        if self.embedder is None:
            raise RuntimeError("Embedder nicht initialisiert")

        embedding = self.embedder.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generiert Embeddings für mehrere Texte (effizient)"""
        if self.embedder is None:
            raise RuntimeError("Embedder nicht initialisiert")

        embeddings = self.embedder.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        return embeddings.tolist()

    def add_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        id_field: str = "id",
        text_field: str = "text",
        batch_size: int = 100,
    ):
        """
        Fügt Dokumente zur Collection hinzu

        Args:
            collection_name: Ziel-Collection
            documents: Liste von Dokumenten mit {id, text, metadata}
            id_field: Feld-Name für ID
            text_field: Feld-Name für Text
            batch_size: Batch-Größe für Embedding-Generierung
        """
        logger.info(f"Füge {len(documents)} Dokumente zu {collection_name} hinzu")

        # Generiere Embeddings in Batches
        texts = [doc[text_field] for doc in documents]

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self.generate_embeddings_batch(batch)
            all_embeddings.extend(embeddings)

        # Erstelle Points
        points = []
        for doc, embedding in zip(documents, all_embeddings):
            # Erstelle ID
            doc_id = doc.get(id_field)
            if doc_id is None:
                doc_id = str(uuid.uuid4())

            # Payload (alles außer text und embedding)
            payload = {k: v for k, v in doc.items() if k != text_field and k != "embedding"}
            payload["text"] = doc[text_field]  # Text auch im Payload speichern

            points.append(PointStruct(id=doc_id, vector=embedding, payload=payload))

        # Upload zu Qdrant
        self.client.upsert(collection_name=collection_name, points=points)

        logger.info(f"✅ {len(points)} Dokumente hinzugefügt")

    def search(
        self,
        collection_name: str,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantische Suche in Collection

        Args:
            collection_name: Collection zum Durchsuchen
            query: Such-Query
            limit: Max. Anzahl Ergebnisse
            score_threshold: Minimaler Similarity-Score
            filters: Optionale Metadaten-Filter

        Returns:
            Liste von Ergebnissen mit score und payload
        """
        # Generiere Query-Embedding
        query_vector = self.generate_embedding(query)

        # Erstelle Filter (optional)
        search_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            if conditions:
                search_filter = Filter(must=conditions)

        # Suche
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=search_filter,
        )

        # Formatiere Ergebnisse
        formatted_results = []
        for result in results:
            formatted_results.append({"id": result.id, "score": result.score, "payload": result.payload})

        return formatted_results

    def get_by_id(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Holt Dokument nach ID"""
        try:
            result = self.client.retrieve(collection_name=collection_name, ids=[doc_id])
            if result:
                return {"id": result[0].id, "payload": result[0].payload}
            return None
        except Exception as e:
            logger.error(f"Fehler beim Abrufen von {doc_id}: {e}")
            return None

    def delete_documents(self, collection_name: str, doc_ids: List[str]):
        """Löscht Dokumente nach IDs"""
        self.client.delete(collection_name=collection_name, points_selector=doc_ids)
        logger.info(f"Gelöscht: {len(doc_ids)} Dokumente aus {collection_name}")

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Holt Collection-Informationen"""
        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error(f"Fehler beim Abrufen von Collection-Info: {e}")
            return {"error": str(e)}

    def list_collections(self) -> List[str]:
        """Listet alle Collections"""
        collections = self.client.get_collections()
        return [c.name for c in collections.collections]


# ============================================================
# SPECIALIZED MANAGERS (für verschiedene Dokumenttypen)
# ============================================================


class LECErrorManager:
    """Manager für LEC-Fehlercode-Dokumente"""

    def __init__(self, db: QdrantVectorDB):
        self.db = db
        self.collection = "lec_errors"

    def add_error(self, error_code: Dict[str, Any]):
        """Fügt einzelnen Fehlercode hinzu"""
        # Text für Embedding: Code + Description + Solutions
        text = (
            f"{error_code['code']}: {error_code['description']} "
            f"Lösungen: {' '.join(error_code.get('solutions', []))}"
        )

        doc = {"id": error_code["code"], "text": text, **error_code}

        self.db.add_documents(self.collection, [doc])

    def search_error(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Sucht Fehlercode"""
        return self.db.search(self.collection, query, limit=limit)

    def get_error_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Holt Fehlercode direkt"""
        return self.db.get_by_id(self.collection, code)


class BMKComponentManager:
    """Manager für BMK-Komponenten"""

    def __init__(self, db: QdrantVectorDB):
        self.db = db
        self.collection = "bmk_components"

    def add_component(self, component: Dict[str, Any]):
        """Fügt Komponente hinzu"""
        text = (
            f"{component['bmk_code']} {component['name']}: "
            f"{component['function_description']} "
            f"Ort: {component['location']}"
        )

        doc = {"id": component["bmk_code"], "text": text, **component}

        self.db.add_documents(self.collection, [doc])

    def search_component(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Sucht Komponenten"""
        return self.db.search(self.collection, query, limit=limit)


class ManualChunkManager:
    """Manager für Handbuch-Chunks"""

    def __init__(self, db: QdrantVectorDB):
        self.db = db
        self.collection = "manuals_chunks"

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """Fügt mehrere Chunks hinzu"""
        self.db.add_documents(self.collection, chunks, id_field="chunk_id")

    def search_manual(self, query: str, model_filter: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Sucht in Handbüchern"""
        filters = {"model_series": model_filter} if model_filter else None
        return self.db.search(self.collection, query, limit=limit, filters=filters)


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def init_kran_doc_database(config: Optional[QdrantConfig] = None) -> QdrantVectorDB:
    """
    Initialisiert komplette Kran-Doc Datenbank

    Returns:
        Konfigurierte QdrantVectorDB
    """
    db = QdrantVectorDB(config)
    db.init_collections()

    logger.info("✅ Kran-Doc Datenbank initialisiert")
    logger.info(f"📊 Collections: {', '.join(db.list_collections())}")

    return db


# ============================================================
# MAIN (für Testing)
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Qdrant Vector Database - Test")
    print("=" * 60)

    if not QDRANT_AVAILABLE:
        print("❌ Qdrant nicht installiert!")
        print("   pip install qdrant-client")
        exit(1)

    if not EMBEDDINGS_AVAILABLE:
        print("❌ Sentence-Transformers nicht installiert!")
        print("   pip install sentence-transformers")
        exit(1)

    # Initialisiere Datenbank
    print("\n🔧 Initialisiere Datenbank...")
    db = init_kran_doc_database()

    # Test: LEC Error hinzufügen
    print("\n📝 Füge Test-Fehlercode hinzu...")
    lec_manager = LECErrorManager(db)
    lec_manager.add_error(
        {
            "code": "LEC-TEST-001",
            "description": "Hydraulikdrucksensor defekt",
            "severity": "critical",
            "solutions": ["Sensor prüfen", "Verkabelung checken", "Sensor tauschen"],
        }
    )

    # Test: Suche
    print("\n🔍 Suche nach 'Hydraulik Problem'...")
    results = lec_manager.search_error("Hydraulik Problem", limit=3)

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result['score']:.3f}")
        print(f"   Code: {result['payload'].get('code')}")
        print(f"   Description: {result['payload'].get('description')}")

    # Collection-Info
    print("\n📊 Collection-Informationen:")
    for collection in db.list_collections():
        info = db.get_collection_info(collection)
        print(f"   {collection}: {info.get('points_count', 0)} Dokumente")

    print("\n✅ Test abgeschlossen!")
