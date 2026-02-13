# Kran-Doc Development Roadmap

**Version:** 2.0  
**Planning Horizon:** 2026 - 2027  
**Last Update:** 16. Januar 2026

---

## 🎯 Vision

Kran-Doc wird zur **führenden Open-Source-Plattform** für technisches Wissensmanagement im Mobilkran-Bereich mit vollständiger Offline-Fähigkeit, KI-Unterstützung und Community-Integration.

---

## 📅 Release Timeline

### Q1 2026: Production Readiness (v2.0 - v2.2) ✅ COMPLETED

**Status:** ✅ Abgeschlossen

#### Milestone 1: Core Architecture ✅

- [x] Core/Adapter Separation für Framework-Unabhängigkeit
- [x] Zentrale Config-Schicht mit Pydantic Settings
- [x] Modularisierung (core, adapters, scripts, webapp)

#### Milestone 2: Job Queue System ✅

- [x] Redis Queue (RQ) Integration
- [x] Job State Machine (uploaded → done/failed)
- [x] Worker für asynchrone Verarbeitung
- [x] JSON-basierte Job-Persistenz
- [x] API Endpoints: /api/import, /api/jobs/<id>

**Deliverables:**
- `scripts/jobs/` Modul mit Worker, Tasks, Models
- API für Job-Management

#### Milestone 3: Provenance & Quellen ✅

- [x] Erweiterte Datenmodelle mit source_document, page_number
- [x] extraction_method, confidence, bbox Felder
- [x] KnowledgeChunk mit vollständiger Provenance
- [x] API gibt immer sources[] zurück
- [x] PDF Viewer Endpoint: /docs/<file>?page=<n>

**Deliverables:**
- Aktualisierte data_models.py
- Source-Link UI Integration

#### Milestone 4: Fusion Search ✅

- [x] Exact Match via Regex (LEC, BMK, Klemmen)
- [x] Fuzzy Match mit RapidFuzz
- [x] Semantic Search via Qdrant
- [x] Fusion Ranking (Exact=1.0, Fuzzy=0.5-0.9, Semantic=0.0-1.0)
- [x] API: /api/search?mode=auto|exact|fuzzy|semantic

**Deliverables:**
- `core/search/fusion_search.py`
- Enhanced Search API

#### Milestone 5: Offline/Sync ✅

- [x] Bundle Export mit Manifest + Checksums
- [x] Bundle Import mit Integrity Check
- [x] Optional: Qdrant Indexing
- [x] CLI Tools: export_bundle.py, import_bundle.py
- [x] API: /api/bundles/import, /api/bundles/list

**Deliverables:**
- `scripts/bundles/` Modul
- Bundle API Endpoints

#### Milestone 6: Security ✅

- [x] In-Memory Rate Limiting
- [x] Upload Protection (size, MIME, filename sanitization)
- [x] Path Traversal Prevention
- [x] API Key Auth (optional)
- [x] Rate Limits: 60/min search, 10/min import

**Deliverables:**
- `adapters/security.py`
- Security decorators

#### Milestone 7: Community Templates ✅

- [x] CommunitySolution Pydantic Model mit required fields
- [x] Validierung beim Submit (reject wenn incomplete)
- [x] Pending Storage: community/solutions_pending.json
- [x] UI Badge: "Community Lösung verfügbar"

**Deliverables:**
- Template Validation
- Structured Community Data

#### Milestone 8: Tests & Docs ✅

- [x] pytest Tests: test_search_fusion.py, test_bundle_manifest.py
- [x] ARCHITECTURE.md Update (Online Server + Offline Kit)
- [x] ROADMAP.md Update (nächste Schritte)

**Deliverables:**
- `tests/` Modul mit Initial Tests
- Aktualisierte Dokumentation

---

### Q2 2026: RAG & Intelligence (v2.3 - v2.5) 📝 NEXT

**Status:** 📝 Geplant

#### Milestone 9: Advanced RAG Pipeline

- [ ] Haystack Integration und Setup
- [ ] DocumentStore ↔ Qdrant Connector
- [ ] Retriever Configuration (EmbeddingRetriever)
- [ ] Custom Pipelines für verschiedene Query-Typen
- [ ] Answer-Generierung mit lokalen LLMs (optional)
- [ ] Query-Expansion und Re-Ranking

**Features:**
- Frage-Antwort über technische Dokumente
- Multi-Dokument-Reasoning
- Quellenangaben und Confidence-Scores

#### Milestone 10: Job Queue Enhancements

- [ ] Retry-Mechanismus bei Fehlern
- [ ] Job-Priorisierung
- [ ] Background Scheduler für Batch-Jobs
- [ ] Monitoring Dashboard
- [ ] Job-History und Analytics

#### Milestone 11: Search Performance

- [ ] Caching-Layer für häufige Queries
- [ ] Aggregierte Collections für schnellere Suche
- [ ] Query-Profiling und Optimization
- [ ] Index Warming auf Startup

---

### Q3 2026: ML-basierte Features (v2.6 - v2.8)

**Status:** 📝 Geplant

#### Milestone 12: ML-basierte Klassifikation

- [ ] Fehlertyp-Klassifikation (Hydraulik, Elektrik, Mechanik)
- [ ] Automatische Severity-Erkennung
- [ ] Komponenten-Typ-Erkennung aus Text
- [ ] Trainingsdaten-Sammlung via Label Studio
- [ ] Model-Training und Evaluation
- [ ] MLflow Integration für Experiment-Tracking

**ML Models:**
- Error Code Classifier
- Component Type Detector
- Severity Predictor
- Document Type Classifier

#### Milestone 13: Knowledge Graph

- [ ] Automatische BMK ↔ LEC Verknüpfung
- [ ] Komponenten-Beziehungen (connected_to)
- [ ] Fehler-Ketten (if A then B)
- [ ] Visualisierung mit NetworkX
- [ ] Graph-basierte Queries
- [ ] Neo4j Integration (optional)

**Deliverables:**
- Knowledge Graph Builder
- Graph-Query-Engine
- Interactive Visualisierungen

---

### Q3 2026: Community & Collaboration (v2.6 - v2.8)

**Status:** 📝 Geplant

#### Milestone 7: Community Solutions System

- [ ] User-Submission-Workflow
- [ ] Review-System mit Rollen (Techniker, Reviewer, Admin)
- [ ] Voting & Rating-System
- [ ] Solution-Templates
- [ ] Multimedia-Support (Bilder, Videos)
- [ ] Automatische Index-Updates nach Approval

**Features:**
- Techniker können Lösungen einreichen
- Review-Queue für Admins
- Community-Voting
- Reputation-System
- Best-Practices-Sammlung

#### Milestone 8: Collaboration Features

- [ ] Multi-User-Support mit Authentication
- [ ] Workspace-Management (pro Firma/Team)
- [ ] Shared Knowledge Bases
- [ ] Kommentar- und Diskussions-System
- [ ] Notification-System (E-Mail, Telegram)
- [ ] Activity-Feed

#### Milestone 9: Advanced Search

- [ ] Fuzzy Search für Tippfehler
- [ ] Autocomplete für Suchanfragen
- [ ] Filters (Model, Year, System, Severity)
- [ ] Saved Searches
- [ ] Search History
- [ ] Advanced Query Syntax

---

### Q4 2026: Advanced Features (v2.9 - v3.0)

**Status:** 💡 Konzept

#### Milestone 10: Multi-Lingualism

- [ ] UI-Übersetzungen (DE, EN, FR, ES, IT, PL)
- [ ] Mehrsprachige Embeddings
- [ ] Automatische Dokumenten-Übersetzung
- [ ] Cross-Language Search
- [ ] Language-Detection

**Target Languages:**
- 🇩🇪 Deutsch (primär)
- 🇬🇧 English
- 🇫🇷 Français
- 🇪🇸 Español
- 🇮🇹 Italiano
- 🇵🇱 Polski

#### Milestone 11: Vision & Advanced OCR

- [ ] SURYA Vision-Transformer Integration
- [ ] Layout-Analyse für komplexe Schaltpläne
- [ ] Handschrift-Erkennung (für Notizen)
- [ ] Diagramm-Interpretation
- [ ] Automatische Annotations

#### Milestone 12: Offline-Optimierung

- [ ] Progressive Web App (PWA)
- [ ] Offline-First Architektur
- [ ] Sync-Mechanismus für Updates
- [ ] Komprimierte Modell-Varianten
- [ ] Edge-Deployment (Raspberry Pi)

**Use Cases:**
- Baustellen ohne Internet
- Werkstatt-Tablets
- Service-Trucks
- Remote Locations

---

## 🔮 Future Vision (2027+)

### Phase 4: Enterprise & Scale

#### Advanced Analytics
- [ ] Usage Analytics und Insights
- [ ] Predictive Maintenance-Integration
- [ ] Trend-Analyse (häufige Fehler)
- [ ] Cost-Tracking für Reparaturen
- [ ] Downtime-Reporting

#### Mobile Apps
- [ ] Native iOS App
- [ ] Native Android App
- [ ] AR-Integration (Komponenten-Overlay)
- [ ] QR-Code-Scanner für BMK-Codes
- [ ] Offline-Sync

#### Integration & APIs
- [ ] ERP-Integration (SAP, etc.)
- [ ] Fleet-Management-Systeme
- [ ] IoT-Sensor-Integration
- [ ] CAN-Bus-Auslese
- [ ] Telematics-Plattformen

#### AI Enhancements
- [ ] Lokales LLM für Antwort-Generierung
- [ ] Image-to-Text für Fehlerfotos
- [ ] Speech-to-Text für Sprachsuche
- [ ] Automatic Report Generation
- [ ] Smart Recommendations

---

## 🎨 Design Priorities

### 1. **Offline-First** 🔌
Alles muss ohne Internet funktionieren

### 2. **Privacy** 🔒
Keine Daten verlassen das System (außer wenn gewünscht)

### 3. **Performance** ⚡
Suche in <500ms, auch bei 100k+ Dokumenten

### 4. **Usability** 🎯
Intuitiv für Techniker, keine Informatik-Kenntnisse nötig

### 5. **Open Source** 🌍
Transparent, Community-getrieben, Fork-freundlich

---

## 📊 Success Metrics

### Technical KPIs
- ✅ **OCR Accuracy:** >95%
- ✅ **Search Latency:** <500ms
- ✅ **Index Size:** <2GB für 10.000 Dokumente
- ✅ **Uptime:** >99.5%

### User KPIs
- 🎯 **Active Users:** 100+ bis Ende 2026
- 🎯 **Documents Indexed:** 50.000+
- 🎯 **Community Solutions:** 500+
- 🎯 **Languages:** 6

---

## 🤝 Community Involvement

### How to Contribute

#### For Developers
- Code-Beiträge via GitHub PRs
- Bug-Reports und Feature-Requests
- Code-Reviews
- Dokumentation

#### For Technicians
- Lösungen einreichen
- Dokumentation testen
- Feedback geben
- Use-Cases teilen

#### For Companies
- Sponsoring
- Beta-Testing
- Data-Sharing (anonymisiert)
- Feature-Funding

---

## 📋 Technical Debt & Refactoring

### Q1-Q2 2026
- [ ] Legacy-Parser-Migration zu Docling
- [ ] Einheitliches Config-System
- [ ] Logging-Standardisierung
- [ ] Error-Handling-Verbesserung
- [ ] Test-Coverage >80%

### Q3-Q4 2026
- [ ] API-Versioning
- [ ] Async-Processing für lange Tasks
- [ ] Caching-Layer
- [ ] Performance-Profiling
- [ ] Security-Audit

---

## 🛠️ Infrastructure Roadmap

### Q1 2026
- [x] Docker Compose Production Stack
- [x] Qdrant Vector DB
- [ ] CI/CD Pipeline (GitHub Actions)
- [ ] Automated Testing
- [ ] Staging Environment

### Q2 2026
- [ ] Kubernetes Manifests (optional)
- [ ] Backup-Strategy
- [ ] Monitoring (Grafana + Prometheus)
- [ ] Log-Aggregation (ELK)
- [ ] High-Availability Setup

### Q3 2026
- [ ] CDN für Static Assets
- [ ] Load Balancer
- [ ] Auto-Scaling
- [ ] Distributed Caching
- [ ] Edge Locations

---

## 💰 Funding & Sustainability

### Current Status
- ✅ Self-funded Development
- ✅ Open Source (MIT License)

### Future Options
- 🎯 GitHub Sponsors
- 🎯 Crowdfunding
- 🎯 Corporate Sponsorships
- 🎯 Paid Support Plans (optional)
- 🎯 Enterprise Features (SaaS)

**Principle:** Core bleibt immer Open Source & kostenlos

---

## 📚 Documentation Roadmap

### Q1 2026
- [x] Architecture Documentation
- [x] Installation Guide
- [x] API Documentation
- [ ] User Guide
- [ ] Developer Guide

### Q2 2026
- [ ] Video-Tutorials
- [ ] Interactive Demos
- [ ] Best-Practices-Guide
- [ ] Troubleshooting-Wiki
- [ ] FAQ

### Q3 2026
- [ ] Multi-Language Docs
- [ ] API-Reference (Swagger/OpenAPI)
- [ ] Code-Examples-Repository
- [ ] Integration-Guides

---

## 🎯 2026 Summary Goals

**By End of Q4 2026:**

✅ **Technology**
- Vollständiges AI-Processing (Docling + OCR)
- RAG mit Haystack
- Multi-Language-Support
- Offline-Fähig

✅ **Features**
- Semantische Suche über alle Dokumenttypen
- Community-Solutions-Platform
- Knowledge Graph
- ML-Klassifikation

✅ **Adoption**
- 100+ aktive Nutzer
- 50.000+ indexierte Dokumente
- 10+ beitragende Entwickler
- 5+ Firmen-Partner

---

**Let's build the future of crane documentation! 🏗️🚀**

**Fragen, Ideen, Feedback?**  
👉 https://github.com/Gregorfun/Kran-doc/discussions

---

**Version:** 2.0  
**Last Update:** 16. Januar 2026  
**Maintainer:** Gregor
