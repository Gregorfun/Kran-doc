from __future__ import annotations

from typing import Any, Callable, Dict

from flask import Blueprint


def create_auth_blueprint(handlers: Dict[str, Callable[..., Any]]) -> Blueprint:
    bp = Blueprint("auth", __name__)

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        return handlers["login"]()

    @bp.route("/account/login", methods=["GET", "POST"])
    def account_login():
        return handlers["account_login"]()

    @bp.route("/account/register", methods=["GET", "POST"])
    def account_register():
        return handlers["account_register"]()

    @bp.route("/account/logout", methods=["POST"])
    def account_logout():
        return handlers["account_logout"]()

    @bp.route("/register", methods=["GET", "POST"])
    def register():
        return handlers["register"]()

    @bp.route("/logout", methods=["POST"])
    def logout():
        return handlers["logout"]()

    return bp
