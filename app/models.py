from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db


def now_utc():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="user")  # user | admin
    created_at = db.Column(db.DateTime, default=now_utc)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class PayrollUpload(db.Model):
    __tablename__ = "payroll_upload"

    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False, default="")  # BPO 고객사명
    payroll_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    file_name = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=now_utc)
    employee_count = db.Column(db.Integer, default=0)
    validation_seconds = db.Column(db.Float, default=0.0)

    uploader = db.relationship("User")
    records = db.relationship("PayrollRecord", backref="upload", cascade="all, delete-orphan")
    results = db.relationship("ValidationResult", backref="upload", cascade="all, delete-orphan")


class PayrollRecord(db.Model):
    """One employee row parsed from an uploaded payroll file."""
    __tablename__ = "payroll_record"

    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("payroll_upload.id"), nullable=False)

    employee_id = db.Column(db.String(32))
    name = db.Column(db.String(64))
    org = db.Column(db.String(64))
    position = db.Column(db.String(64))
    base_pay = db.Column(db.Float)
    allowance = db.Column(db.Float)
    bonus = db.Column(db.Float)
    deduction = db.Column(db.Float)
    net_pay = db.Column(db.Float)


class ValidationRule(db.Model):
    __tablename__ = "validation_rule"

    id = db.Column(db.Integer, primary_key=True)
    rule_code = db.Column(db.String(32), unique=True, nullable=False)
    rule_name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(255))
    severity = db.Column(db.String(16), nullable=False, default="WARNING")  # CRITICAL|WARNING|INFO
    threshold = db.Column(db.Float, nullable=True)  # e.g. 0.3 for 30%
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_utc)


class ValidationResult(db.Model):
    __tablename__ = "validation_result"

    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("payroll_upload.id"), nullable=False)
    employee_id = db.Column(db.String(32))
    employee_name = db.Column(db.String(64))
    org = db.Column(db.String(64))

    rule_id = db.Column(db.Integer, db.ForeignKey("validation_rule.id"), nullable=False)
    result_text = db.Column(db.String(255))  # human readable description
    severity = db.Column(db.String(16), nullable=False)
    detected_value = db.Column(db.String(64))
    expected_value = db.Column(db.String(64))

    status = db.Column(db.String(16), nullable=False, default="미처리")  # 미처리|검토중|정상|수정완료
    created_at = db.Column(db.DateTime, default=now_utc)

    rule = db.relationship("ValidationRule")
    resolutions = db.relationship("ResolutionHistory", backref="validation_result", cascade="all, delete-orphan")


class ResolutionHistory(db.Model):
    __tablename__ = "resolution_history"

    id = db.Column(db.Integer, primary_key=True)
    validation_result_id = db.Column(db.Integer, db.ForeignKey("validation_result.id"), nullable=False)
    status = db.Column(db.String(16), nullable=False)
    reason = db.Column(db.String(500))
    resolved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    resolved_at = db.Column(db.DateTime, default=now_utc)

    resolver = db.relationship("User")
