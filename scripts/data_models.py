"""
Datenmodelle für Kran-Doc System
=================================

Strukturierte Pydantic-Modelle für alle Dokumenttypen:
- LEC Fehlercode
- BMK Komponente
- SPL Schaltplan
- Community-Lösungen

Author: Gregor
Version: 2.0
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

# ============================================================
# ENUMS
# ============================================================


class Severity(str, Enum):
    """Fehler-Schweregrad"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ReviewStatus(str, Enum):
    """Review-Status für Community-Beiträge"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class Difficulty(str, Enum):
    """Schwierigkeitsgrad für Reparaturen"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class ComponentType(str, Enum):
    """BMK Komponententypen"""

    MOTOR = "motor"
    SENSOR = "sensor"
    RELAY = "relay"
    SWITCH = "switch"
    CONTROLLER = "controller"
    ACTUATOR = "actuator"
    VALVE = "valve"
    PUMP = "pump"
    DISPLAY = "display"
    CONNECTOR = "connector"
    FUSE = "fuse"
    OTHER = "other"


class SignalType(str, Enum):
    """Signal-Typen"""

    DIGITAL = "digital"
    ANALOG = "analog"
    PWM = "pwm"
    CAN = "can"
    POWER = "power"
    GROUND = "ground"


# ============================================================
# LEC FEHLERCODE
# ============================================================


class LECErrorCode(BaseModel):
    """
    LEC Fehlercode Datenmodell

    Beispiel:
    {
        "code": "LEC-12345",
        "description": "Hydraulikdrucksensor defekt",
        "severity": "critical",
        "affected_systems": ["Hydraulik", "Steuerung"],
        "possible_causes": ["Kabelbruch", "Sensor defekt"],
        "solutions": ["Verkabelung prüfen", "Sensor tauschen"]
    }
    """

    code: str = Field(..., description="LEC Fehlercode, z.B. LEC-12345")
    description: str = Field(..., description="Fehlerbeschreibung")
    severity: Severity = Field(..., description="Schweregrad des Fehlers")

    affected_systems: List[str] = Field(
        default_factory=list, description="Betroffene Systeme (Hydraulik, Elektrik, etc.)"
    )

    possible_causes: List[str] = Field(default_factory=list, description="Mögliche Fehlerursachen")

    solutions: List[str] = Field(default_factory=list, description="Lösungsschritte")

    related_bmk: List[str] = Field(default_factory=list, description="Zugehörige BMK-Codes")

    related_spl: List[str] = Field(default_factory=list, description="Zugehörige SPL-Dokumente")

    model_series: List[str] = Field(
        default_factory=list, description="Betroffene Kranmodelle (z.B. LTM 1070, LTM 1100)"
    )

    source_document: str = Field(..., description="Quelldokument (PDF-Datei)")
    page_number: int = Field(..., description="Seitennummer im Dokument", ge=1)
    extraction_method: Optional[str] = Field(None, description="Extraktionsmethode (docling|unstructured|ocr)")

    confidence: float = Field(default=1.0, description="Extraktions-Konfidenz (0-1)", ge=0.0, le=1.0)

    bbox: Optional[Dict[str, float]] = Field(None, description="Bounding Box im Dokument {x, y, w, h}")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Zusätzliche Metadaten")

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @validator("code")
    def validate_code(cls, v):
        """Validiert LEC-Code Format"""
        if not v.startswith("LEC-"):
            raise ValueError("Code muss mit LEC- beginnen")
        return v.upper()

    class Config:
        json_schema_extra = {
            "example": {
                "code": "LEC-12345",
                "description": "Hydraulikdrucksensor defekt",
                "severity": "critical",
                "affected_systems": ["Hydraulik", "Steuerung"],
                "possible_causes": ["Kabelbruch", "Sensor defekt", "Verschmutzung"],
                "solutions": ["Verkabelung prüfen", "Sensor tauschen", "Anschlüsse reinigen"],
                "related_bmk": ["B1-S4", "B2-M7"],
                "model_series": ["LTM 1070-4.2", "LTM 1090-4.2"],
                "source_document": "LEC_LTM1070_v3.pdf",
                "page_number": 42,
            }
        }


# ============================================================
# BMK KOMPONENTE
# ============================================================


class BMKComponent(BaseModel):
    """
    BMK Bauteilliste Komponente

    Beschreibt eine einzelne Komponente mit allen Eigenschaften,
    Signalen und Verbindungen.
    """

    bmk_code: str = Field(..., description="BMK-Code, z.B. B1-M1")
    component_type: ComponentType = Field(..., description="Komponententyp")

    name: str = Field(..., description="Komponenten-Name")
    description: str = Field(default="", description="Detaillierte Beschreibung")

    manufacturer: Optional[str] = Field(None, description="Hersteller")
    part_number: Optional[str] = Field(None, description="Teilenummer")
    serial_number: Optional[str] = Field(None, description="Seriennummer (falls relevant)")

    # Lokation
    location: str = Field(..., description="Einbauort (z.B. Hauptschaltschrank)")
    location_details: Optional[str] = Field(None, description="Detaillierte Position")
    coordinates: Optional[Dict[str, float]] = Field(None, description="Koordinaten im Schaltplan (x, y)")

    # Elektrische Eigenschaften
    signals: List[Dict[str, Any]] = Field(
        default_factory=list, description="Signale: [{signal_name, type, voltage, pin}]"
    )

    voltage: Optional[str] = Field(None, description="Betriebsspannung (z.B. 24V DC)")
    current: Optional[str] = Field(None, description="Stromaufnahme (z.B. 2A)")
    power: Optional[str] = Field(None, description="Leistung (z.B. 48W)")

    # Funktion
    function_description: str = Field(..., description="Funktionsbeschreibung")

    # Verbindungen
    connected_to: List[str] = Field(default_factory=list, description="Verbundene BMK-Codes")

    used_in_spl: List[str] = Field(default_factory=list, description="Verwendung in SPL-Dokumenten")

    # Dokumentation
    source_document: str = Field(..., description="Quelldokument")
    page_number: Optional[int] = Field(None, description="Seite im Dokument", ge=1)
    extraction_method: Optional[str] = Field(None, description="Extraktionsmethode (docling|unstructured|ocr)")

    model_series: List[str] = Field(default_factory=list, description="Kranmodelle")

    # Status & Wartung
    maintenance_interval: Optional[str] = Field(None, description="Wartungsintervall (z.B. '1000h' oder '1 Jahr')")

    replacement_parts: List[str] = Field(default_factory=list, description="Ersatzteile (Teilenummern)")

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @validator("bmk_code")
    def validate_bmk_code(cls, v):
        """Validiert BMK-Code Format (z.B. B1-M1, A3-S7)"""
        import re

        if not re.match(r"^[A-Z]\d+-[A-Z]\d+$", v):
            raise ValueError("BMK-Code muss Format [A-Z][0-9]-[A-Z][0-9] haben")
        return v.upper()

    class Config:
        json_schema_extra = {
            "example": {
                "bmk_code": "B1-M1",
                "component_type": "motor",
                "name": "Hauptantriebsmotor",
                "manufacturer": "Siemens",
                "part_number": "1LA7-090-4AA60",
                "location": "Hauptschaltschrank, Reihe 1",
                "signals": [
                    {"name": "U", "type": "power", "voltage": "400V AC", "pin": 1},
                    {"name": "V", "type": "power", "voltage": "400V AC", "pin": 2},
                    {"name": "W", "type": "power", "voltage": "400V AC", "pin": 3},
                ],
                "voltage": "400V AC",
                "function_description": "Hauptantrieb für Drehwerk",
                "connected_to": ["B1-K1", "B1-F1"],
                "source_document": "BMK_LTM1070.pdf",
                "page_number": 15,
            }
        }


# ============================================================
# SPL SCHALTPLAN
# ============================================================


class Terminal(BaseModel):
    """Einzelne Klemme/Terminal"""

    terminal_id: str = Field(..., description="Klemmen-ID (z.B. X1:1)")
    signal_name: str = Field(..., description="Signal-Name")
    signal_type: SignalType = Field(..., description="Signal-Typ")
    voltage: Optional[str] = Field(None, description="Spannung")
    connected_component: Optional[str] = Field(None, description="Verbundene Komponente (BMK)")


class Connection(BaseModel):
    """Elektrische Verbindung"""

    from_terminal: str = Field(..., description="Start-Klemme")
    to_terminal: str = Field(..., description="Ziel-Klemme")
    wire_color: Optional[str] = Field(None, description="Kabelfarbe")
    wire_gauge: Optional[str] = Field(None, description="Kabelquerschnitt (mm²)")
    cable_number: Optional[str] = Field(None, description="Kabelnummer")


class SPLCircuit(BaseModel):
    """
    SPL Stromlaufplan Datenmodell

    Beschreibt einen vollständigen Schaltkreis mit allen
    Verbindungen und Komponenten.
    """

    circuit_id: str = Field(..., description="Schaltkreis-ID")
    circuit_name: str = Field(..., description="Schaltkreis-Name")
    description: str = Field(default="", description="Beschreibung")

    # Terminals
    terminals: List[Terminal] = Field(default_factory=list, description="Liste aller Klemmen")

    # Komponenten
    components: List[str] = Field(default_factory=list, description="BMK-Codes aller Komponenten im Schaltkreis")

    # Verbindungen
    connections: List[Connection] = Field(default_factory=list, description="Alle elektrischen Verbindungen")

    # Power Supply
    power_supply: str = Field(..., description="Stromversorgung (z.B. 24V DC)")
    voltage_level: Optional[str] = Field(None, description="Spannungsebene")

    # Schutzeinrichtungen
    protection_devices: List[str] = Field(default_factory=list, description="Sicherungen, Relais, etc. (BMK-Codes)")

    fuse_rating: Optional[str] = Field(None, description="Sicherungswert")

    # Dokumentation
    source_document: str = Field(..., description="Quelldokument")
    page_number: int = Field(..., description="Seite", ge=1)
    extraction_method: Optional[str] = Field(None, description="Extraktionsmethode (docling|unstructured|ocr)")
    bbox: Optional[Dict[str, float]] = Field(None, description="Bounding Box {x, y, w, h}")

    model_series: List[str] = Field(default_factory=list, description="Kranmodelle")

    # Metadaten
    diagram_type: Optional[str] = Field(None, description="Diagramm-Typ (Übersicht, Detail, etc.)")

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "circuit_id": "SPL-001-H1",
                "circuit_name": "Haupthydraulikpumpe",
                "terminals": [
                    {"terminal_id": "X1:1", "signal_name": "+24V", "signal_type": "power", "voltage": "24V DC"}
                ],
                "components": ["B1-M1", "B1-S1", "B1-K1"],
                "power_supply": "24V DC",
                "source_document": "SPL_LTM1070_Hydraulik.pdf",
                "page_number": 8,
            }
        }


# ============================================================
# COMMUNITY SOLUTION
# ============================================================


class CommunitySolution(BaseModel):
    """
    Community-Lösung von Technikern

    Sammlung von praktischen Lösungen und Workarounds
    aus dem Feld.
    """

    solution_id: str = Field(..., description="Eindeutige Solution-ID")

    # Zuordnung
    related_error_codes: List[str] = Field(default_factory=list, description="Zugehörige LEC-Codes")

    related_components: List[str] = Field(default_factory=list, description="Betroffene BMK-Codes")

    model_series: List[str] = Field(default_factory=list, description="Kranmodelle")

    # Problem & Lösung
    problem_description: str = Field(..., description="Problembeschreibung")

    symptoms: List[str] = Field(default_factory=list, description="Symptome des Problems")

    root_cause: Optional[str] = Field(None, description="Grundursache (falls bekannt)")

    solution_steps: List[str] = Field(..., description="Lösungsschritte (geordnet)")

    # Ressourcen
    required_parts: List[Dict[str, str]] = Field(
        default_factory=list, description="Benötigte Teile: [{part_number, description, quantity}]"
    )

    required_tools: List[str] = Field(default_factory=list, description="Benötigtes Werkzeug")

    special_equipment: List[str] = Field(default_factory=list, description="Spezialwerkzeug oder Messgeräte")

    # Aufwand
    estimated_time: int = Field(..., description="Geschätzte Zeit in Minuten", ge=1)

    difficulty: Difficulty = Field(..., description="Schwierigkeitsgrad")

    safety_warnings: List[str] = Field(default_factory=list, description="Sicherheitshinweise")

    # Community
    submitted_by: str = Field(..., description="Einreicher (Username)")
    submitted_email: Optional[str] = Field(None, description="E-Mail (optional)")
    company: Optional[str] = Field(None, description="Firma (optional)")

    reviewed_by: Optional[str] = Field(None, description="Reviewer")
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING, description="Review-Status")

    review_comments: Optional[str] = Field(None, description="Review-Kommentare")

    # Rating
    votes: int = Field(default=0, description="Community-Votes")
    success_rate: Optional[float] = Field(None, description="Erfolgsrate (0-1)", ge=0.0, le=1.0)

    times_applied: int = Field(default=0, description="Wie oft wurde diese Lösung angewendet")

    # Multimedia
    images: List[str] = Field(default_factory=list, description="Bild-URLs oder Pfade")

    videos: List[str] = Field(default_factory=list, description="Video-URLs")

    documents: List[str] = Field(default_factory=list, description="Zusätzliche Dokumente")

    # Tags & Kategorien
    tags: List[str] = Field(default_factory=list, description="Tags für Filterung")

    category: Optional[str] = Field(None, description="Kategorie (Hydraulik, Elektrik, etc.)")

    # Zeitstempel
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    approved_at: Optional[datetime] = Field(None)

    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "solution_id": "SOL-2024-001",
                "related_error_codes": ["LEC-12345"],
                "model_series": ["LTM 1070-4.2"],
                "problem_description": "Hydraulikdrucksensor zeigt intermittierenden Fehler",
                "symptoms": ["Sporadischer LEC-12345", "Druckanzeige schwankt"],
                "solution_steps": [
                    "Sensor-Stecker trennen und reinigen",
                    "Kontakte mit Kontaktspray behandeln",
                    "Kabelbaum auf Scheuerstellen prüfen",
                    "Sensor neu kalibrieren",
                ],
                "required_parts": [
                    {"part_number": "12345-ABC", "description": "Drucksensor (falls defekt)", "quantity": "1"}
                ],
                "required_tools": ["Multimeter", "Kontaktspray", "Schraubendreher-Set"],
                "estimated_time": 45,
                "difficulty": "medium",
                "submitted_by": "technik_max",
                "votes": 15,
            }
        }


# ============================================================
# KNOWLEDGE CHUNK (für Embeddings)
# ============================================================


class KnowledgeChunk(BaseModel):
    """
    Chunk von Wissen für Vektor-Embeddings

    Verwendet für semantische Suche.
    """

    chunk_id: str = Field(..., description="Eindeutige Chunk-ID")

    source_type: str = Field(..., description="Quellentyp: lec, bmk, spl, manual, community")

    source_id: str = Field(..., description="ID des Quell-Objekts")
    source_document: Optional[str] = Field(None, description="Quelldokument")
    page_number: Optional[int] = Field(None, description="Seitennummer", ge=1)
    extraction_method: Optional[str] = Field(None, description="Extraktionsmethode")
    confidence: Optional[float] = Field(None, description="Konfidenz", ge=0.0, le=1.0)
    bbox: Optional[Dict[str, float]] = Field(None, description="Bounding Box {x, y, w, h}")

    text: str = Field(..., description="Text-Inhalt für Embedding")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadaten (Modell, Seite, etc.)")

    embedding: Optional[List[float]] = Field(None, description="Vektor-Embedding (wird automatisch erzeugt)")

    created_at: datetime = Field(default_factory=datetime.now)


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    "Severity",
    "ReviewStatus",
    "Difficulty",
    "ComponentType",
    "SignalType",
    "LECErrorCode",
    "BMKComponent",
    "Terminal",
    "Connection",
    "SPLCircuit",
    "CommunitySolution",
    "KnowledgeChunk",
]
