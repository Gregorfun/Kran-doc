"""
API Documentation & OpenAPI Schema for Kran-Doc

This module provides API documentation and generates OpenAPI specifications
for the Flask application endpoints.

Endpoints documented:
- /api/status          - System status check
- /api/search          - Semantic search
- /api/bmk_search      - BMK component search
- /api/ersatzteile     - Spare parts search
- /api/feedback        - Feedback submission
- /api/import          - PDF import
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# OpenAPI Specification for Kran-Doc API
OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Kran-Doc API",
        "description": "AI-powered documentation platform for mobile crane technicians",
        "version": "2.0.0",
        "contact": {
            "name": "PDFDoc Team",
            "url": "https://github.com/Gregorfun/Kran-doc",
        },
    },
    "servers": [
        {
            "url": "http://localhost:5002",
            "description": "Development server",
        },
        {
            "url": "http://0.0.0.0:5002",
            "description": "Production server (adjust host as needed)",
        },
    ],
    "paths": {
        "/api/status": {
            "get": {
                "summary": "Get system status",
                "description": "Returns current system status including embeddings availability",
                "operationId": "api_status",
                "responses": {
                    "200": {
                        "description": "System status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {"type": "boolean"},
                                        "status": {
                                            "type": "object",
                                            "properties": {
                                                "embedding_index_available": {"type": "boolean"},
                                                "num_models": {"type": "integer"},
                                                "models_dir": {"type": "string"},
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/search": {
            "post": {
                "summary": "Semantic search",
                "description": "Search documentation using semantic embeddings",
                "operationId": "api_search",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string", "description": "Search query"},
                                    "model": {"type": "string", "description": "Crane model (optional)"},
                                    "top_k": {
                                        "type": "integer",
                                        "default": 5,
                                        "description": "Number of results",
                                    },
                                    "source_type": {
                                        "type": "string",
                                        "enum": ["lec_error", "bmk", "manual", "all"],
                                        "description": "Filter by source type (optional)",
                                    },
                                },
                                "required": ["question", "model"],
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Search results",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {"type": "boolean"},
                                        "results": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "title": {"type": "string"},
                                                    "description": {"type": "string"},
                                                    "source_type": {"type": "string"},
                                                    "score": {"type": "number"},
                                                },
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "400": {"description": "Invalid request"},
                    "500": {"description": "Server error"},
                },
            }
        },
        "/api/bmk_search": {
            "post": {
                "summary": "BMK component search",
                "description": "Search for BMK (component) information",
                "operationId": "api_bmk_search",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "model": {"type": "string", "description": "Crane model"},
                                    "bmk_code": {
                                        "type": "string",
                                        "description": "BMK component code",
                                    },
                                },
                                "required": ["model", "bmk_code"],
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Component information"},
                    "404": {"description": "Component not found"},
                },
            }
        },
        "/api/feedback": {
            "post": {
                "summary": "Submit feedback",
                "description": "Submit feedback about search results",
                "operationId": "api_feedback",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "result": {"type": "object"},
                                    "note": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Feedback recorded",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {"type": "boolean"}
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/import": {
            "post": {
                "summary": "Import PDF",
                "description": "Import a new PDF document",
                "operationId": "api_import",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "PDF file",
                                    },
                                    "model": {
                                        "type": "string",
                                        "description": "Crane model (optional)",
                                    },
                                },
                                "required": ["file"],
                            }
                        }
                    },
                },
                "responses": {
                    "202": {
                        "description": "Import job started",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "job_id": {"type": "string"},
                                        "status": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "400": {"description": "Invalid file or request"},
                    "429": {"description": "Rate limit exceeded"},
                },
            }
        },
    },
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            }
        }
    },
    "security": [{"ApiKeyAuth": []}],
}


def get_openapi_spec() -> Dict[str, Any]:
    """Return OpenAPI specification."""
    return OPENAPI_SPEC


def register_openapi_routes(app: Any) -> None:
    """Register OpenAPI documentation routes."""
    from flask import jsonify

    @app.route("/api/docs", methods=["GET"])
    def api_docs():
        """Return OpenAPI specification."""
        return jsonify(OPENAPI_SPEC)

    @app.route("/api/docs/openapi.json", methods=["GET"])
    def api_docs_json():
        """Return OpenAPI specification (for Swagger UI)."""
        return jsonify(OPENAPI_SPEC)


# API Response Format Guidelines

"""
Standard API Responses:

SUCCESS (200/202):
{
    "ok": true,
    "data": {...},
    "message": "Operation successful"
}

ERROR (4xx/5xx):
{
    "ok": false,
    "error": "Error description",
    "code": "ERROR_CODE"
}

PAGINATED:
{
    "ok": true,
    "data": [...],
    "pagination": {
        "total": 100,
        "page": 1,
        "limit": 10,
        "pages": 10
    }
}
"""

# Example endpoints for documentation

API_EXAMPLES = {
    "search_query": {
        "method": "POST",
        "url": "/api/search",
        "body": {
            "question": "Hydraulikdruck zu niedrig",
            "model": "LTM1200-5.1",
            "top_k": 5,
            "source_type": "lec_error",
        },
        "response": {
            "ok": True,
            "results": [
                {
                    "title": "Hydraulik Drucksensor",
                    "description": "Der Hydraulikdrucksensor misst...",
                    "score": 0.92,
                    "source_type": "lec_error",
                    "model": "LTM1200-5.1",
                    "explain": {
                        "next_steps": [
                            "Prüfe Sensorverkabelung",
                            "Messe Hydraulikdruck",
                            "Tausche Sensor aus falls nötig",
                        ]
                    },
                }
            ],
        },
    },
    "status_check": {
        "method": "GET",
        "url": "/api/status",
        "response": {
            "ok": True,
            "status": {
                "embedding_index_available": True,
                "num_models": 5,
                "models_dir": "/app/output/models",
                "has_chunks_jsonl": True,
            },
        },
    },
}
