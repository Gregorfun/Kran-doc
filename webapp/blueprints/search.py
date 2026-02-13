from __future__ import annotations

from typing import Any, Callable, Dict

from flask import Blueprint


def create_search_blueprint(handlers: Dict[str, Callable[..., Any]]) -> Blueprint:
    bp = Blueprint("search", __name__)

    @bp.route("/api/status", methods=["GET"])
    def api_status():
        return handlers["api_status"]()

    @bp.route("/health", methods=["GET"])
    def health():
        return handlers["health"]()

    @bp.route("/api/search", methods=["POST"])
    def api_search():
        return handlers["api_search"]()

    @bp.route("/api/search/fusion", methods=["GET", "POST"])
    def api_search_fusion():
        return handlers["api_search_fusion"]()

    return bp
