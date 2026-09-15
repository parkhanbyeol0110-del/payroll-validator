from .extensions import db
from .models import User, ValidationRule

DEFAULT_RULES = [
    dict(rule_code="RULE_001", rule_name="사번 중복", description="동일 사번이 2건 이상 존재",
         severity="CRITICAL", threshold=None),
    dict(rule_code="RULE_002", rule_name="필수값 누락", description="사번/성명/조직/급여 등 필수 컬럼 누락",
         severity="CRITICAL", threshold=None),
    dict(rule_code="RULE_003", rule_name="음수 급여", description="기본급이 0보다 작음",
         severity="CRITICAL", threshold=None),
    dict(rule_code="RULE_004", rule_name="계산 불일치", description="기본급+수당+상여-공제 != 실지급액",
         severity="CRITICAL", threshold=None),
    dict(rule_code="RULE_005", rule_name="전월 대비 급여 급증/급감", description="전월 대비 실지급액 변동률이 임계값을 초과",
         severity="WARNING", threshold=0.3),
    dict(rule_code="RULE_006", rule_name="신규 입사자", description="전월에 없던 사번이 당월에 새로 등장",
         severity="INFO", threshold=None),
    dict(rule_code="RULE_007", rule_name="퇴사자(전월 대비 누락)", description="전월에 있던 사번이 당월에 존재하지 않음",
         severity="INFO", threshold=None),
]


def seed_defaults():
    if ValidationRule.query.count() == 0:
        for r in DEFAULT_RULES:
            db.session.add(ValidationRule(**r))
        db.session.commit()

    if User.query.count() == 0:
        admin = User(username="admin", name="관리자", role="admin")
        admin.set_password("admin1234")
        db.session.add(admin)
        db.session.commit()
