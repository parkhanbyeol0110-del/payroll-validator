# 급여 마감 전 검증 보조 시스템 (MVP)

PRD Phase 1(Rule-Based) ~ 이력 축적까지 구현한 MVP입니다.

## 실행 방법

```bash
cd payroll-validator
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python run.py
```

브라우저에서 http://127.0.0.1:5000 접속. 기본 관리자 계정: `admin` / `admin1234`

첫 실행 시 `instance/payroll.db` (SQLite)가 자동 생성되고 기본 검증 Rule 7종과 관리자 계정이 시드됩니다.

## 구현된 기능 (PRD 20장 MVP 범위)

- 로그인 / 로그아웃 (Flask-Login)
- 급여 파일 업로드 (xlsx/xls/csv, `app/upload.py`)
- Excel/CSV 파싱 및 필수 컬럼 검증 (`app/validation/engine.py`)
- Rule-Based 검증 7종 (`app/seed.py`에 정의, `validation_rule` 테이블에서 관리)
  - RULE_001 사번 중복 (CRITICAL)
  - RULE_002 필수값 누락 (CRITICAL)
  - RULE_003 음수 급여 (CRITICAL)
  - RULE_004 계산 불일치: 기본급+수당+상여-공제 ≠ 실지급액 (CRITICAL)
  - RULE_005 전월 대비 급여 변동률 초과, 기본 임계값 ±30% (WARNING)
  - RULE_006 신규 입사자 (INFO)
  - RULE_007 퇴사 추정 (전월 대비 누락) (INFO)
- 오류 유형 분류 및 심각도(CRITICAL/WARNING/INFO) 표시
- 검증 결과 Dashboard (Chart.js, 로컬 번들 `app/static/js/chart.umd.min.js`)
- 오류 상세 조회 (심각도/처리상태 필터)
- 담당자 처리 상태 변경 + 처리 사유 기록 (`resolution_history` 테이블 → 향후 ML 학습 Label로 활용 예정)
- 검증 이력 저장 및 업로드별/월별 KPI 집계 (`/history`)
- 재검증 (Rule 활성화/기준값 변경 후 기존 업로드에 대해 재실행)
- 관리자 전용 Rule 관리 화면 (`/rules`): 활성화 토글, 임계값(threshold) 수정

## 샘플 데이터

`sample_data/payroll_2026_01.csv`, `sample_data/payroll_2026_02.csv` — 2월 파일에는 7종 Rule을 모두 재현하는 의도적 오류가 포함되어 있습니다 (사번 중복, 필수값 누락, 음수 급여, 계산 불일치, 급여 급증, 신규 입사자, 퇴사 추정).

## 알려진 제한사항 / 다음 단계

- 재검증(`/uploads/<id>/revalidate`)은 기존 검증 결과를 전부 삭제 후 재생성하므로, 이미 입력된 처리 상태/사유(`resolution_history`)도 함께 사라집니다. Phase 2에서는 사번+Rule 기준으로 기존 이력을 유지한 채 병합하는 방식으로 개선이 필요합니다.
- DB는 SQLite (로컬 개발용). 운영 전환 시 PostgreSQL로 `SQLALCHEMY_DATABASE_URI`만 교체하면 됩니다.
- PRD Phase 3(업무량/패턴 분석 고도화), Phase 4(통계 기반 기준), Phase 5(ML 예측)는 미구현이며, `resolution_history`에 축적되는 처리 사유 데이터가 향후 ML 학습 Label의 기반이 됩니다.
