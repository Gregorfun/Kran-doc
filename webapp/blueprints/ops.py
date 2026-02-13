from __future__ import annotations

from typing import Any, Callable, Dict

from flask import Blueprint


def create_ops_blueprint(handlers: Dict[str, Callable[..., Any]]) -> Blueprint:
    bp = Blueprint("ops", __name__)

    @bp.route("/api/import", methods=["POST"])
    def api_import():
        return handlers["api_import"]()

    @bp.route("/api/jobs/<job_id>", methods=["GET"])
    def api_job_status(job_id: str):
        return handlers["api_job_status"](job_id)

    @bp.route("/api/jobs/<job_id>/log", methods=["GET"])
    def api_job_log(job_id: str):
        return handlers["api_job_log"](job_id)

    @bp.route("/api/bundles/import", methods=["POST"])
    def api_bundle_import():
        return handlers["api_bundle_import"]()

    @bp.route("/api/bundles/list", methods=["GET"])
    def api_bundle_list():
        return handlers["api_bundle_list"]()

    @bp.route("/docs/<path:filename>")
    def view_document(filename: str):
        return handlers["view_document"](filename)

    return bp
