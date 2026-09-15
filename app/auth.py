from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard.index"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("현재 비밀번호가 올바르지 않습니다.", "error")
        elif len(new_password) < 8:
            flash("새 비밀번호는 8자 이상이어야 합니다.", "error")
        elif new_password != confirm_password:
            flash("새 비밀번호가 일치하지 않습니다.", "error")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("비밀번호가 변경되었습니다.", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("change_password.html")
