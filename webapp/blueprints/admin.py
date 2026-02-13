from __future__ import annotations

from typing import Any, Callable, Dict

from flask import Blueprint


def create_admin_blueprint(handlers: Dict[str, Callable[..., Any]]) -> Blueprint:
    bp = Blueprint("admin", __name__)

    @bp.route("/admin", methods=["GET"])
    def admin_dashboard():
        return handlers["admin_dashboard"]()

    @bp.route("/admin/users", methods=["GET"])
    def admin_users():
        return handlers["admin_users"]()

    @bp.route("/admin/users/<user_id>/approve", methods=["POST"])
    def admin_user_approve(user_id: str):
        return handlers["admin_user_approve"](user_id)

    @bp.route("/admin/users/<user_id>/reject", methods=["POST"])
    def admin_user_reject(user_id: str):
        return handlers["admin_user_reject"](user_id)

    @bp.route("/admin/solutions", methods=["GET"])
    def admin_solutions():
        return handlers["admin_solutions"]()

    @bp.route("/admin/solutions/<solution_id>/approve", methods=["POST"])
    def admin_solution_approve(solution_id: str):
        return handlers["admin_solution_approve"](solution_id)

    @bp.route("/admin/solutions/<solution_id>/reject", methods=["POST"])
    def admin_solution_reject(solution_id: str):
        return handlers["admin_solution_reject"](solution_id)

    @bp.route("/admin/community/review", methods=["GET"])
    def community_review():
        return handlers["community_review"]()

    @bp.route("/admin/community/approve/<solution_id>", methods=["POST"])
    def community_approve(solution_id: str):
        return handlers["community_approve"](solution_id)

    @bp.route("/admin/community/reject/<solution_id>", methods=["POST"])
    def community_reject(solution_id: str):
        return handlers["community_reject"](solution_id)

    return bp
