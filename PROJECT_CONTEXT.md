# 프로젝트 컨텍스트 — 급여 마감 전 검증 보조 시스템 (Payroll Validator)

> 다른 AI 코딩 도구(Codex, Cursor 등)에 이 프로젝트를 이어서 맡길 때 참고할 수 있도록,
> 지금까지 한 작업을 기술/기획 양면에서 정리한 문서입니다. 이 저장소 루트에 그대로 두면
> 대부분의 AI 코딩 툴이 컨텍스트로 자동 인식합니다.

## 한 줄 요약

BPO가 여러 고객사의 급여를 마감하기 전, 업로드 한 번으로 오류·이상 데이터를 자동 탐지하고
처리 이력을 쌓아가는 Rule 기반 급여 검증 대시보드.

## 배포/저장소

| 항목 | 값 |
|---|---|
| 프로덕션 URL | https://payroll-validator-rho.vercel.app |
| GitHub 저장소 | https://github.com/parkhanbyeol0110-del/payroll-validator (Public) |
| Vercel 프로젝트 | `payroll-validator` (parkhanbyeol0110-del) |
| DB | Supabase PostgreSQL (`payroll-validator-db`), Vercel Storage 통합으로 연결 |
| 배포 방식 | GitHub `master` 브랜치 push → Vercel 자동 배포 (수동 `vercel deploy` 불필요) |
| 관리자 계정 | `admin` / 비밀번호는 로테이션됨 — 별도 채널로 전달, 이 문서에는 기재하지 않음 |

## 기술 스택

- **Backend**: Python Flask, Flask-SQLAlchemy, Flask-Login (세션 기반 인증)
- **DB**: 로컬 개발은 SQLite(`instance/payroll.db`), 운영은 PostgreSQL(Supabase). `POSTGRES_URL`/`DATABASE_URL` 환경변수 존재 여부로 `app/__init__.py`의 `_configure_database()`가 자동 분기
- **프론트엔드**: 서버 렌더링(Jinja2) + AG Grid(테이블 정렬/필터/페이지네이션) + Chart.js(시각화) + SheetJS(엑셀 내보내기, 업로드 전 미리보기). 세 라이브러리 모두 CDN이 아닌 `app/static/vendor/`에 로컬로 번들링(서버리스 환경에서 외부 네트워크 의존 제거 목적)
- **배포**: Vercel `@vercel/python` 런타임 (`vercel.json` 참고). Vercel 파일시스템이 읽기 전용이라, 업로드된 파일은 디스크에 저장하지 않고 메모리에서 바로 파싱

## 디렉토리 구조

```
payroll-validator/
├── app/
│   ├── __init__.py          # 앱 팩토리, DB 설정 분기, 경량 마이그레이션
│   ├── models.py            # User, PayrollUpload, PayrollRecord, ValidationRule, ValidationResult, ResolutionHistory
│   ├── auth.py               # 로그인/로그아웃/비밀번호 변경
│   ├── upload.py             # 파일 업로드 + 검증 실행
│   ├── dashboard.py          # 대시보드/상세/조직별 통계/이력/Rule 관리 라우트
│   ├── seed.py                # 초기 Rule 7종 + admin 계정 시드
│   ├── validation/engine.py   # Rule-Based 검증 엔진 (핵심 로직)
│   ├── templates/             # Jinja2 템플릿 (base.html이 사이드바 레이아웃)
│   └── static/
│       ├── vendor/            # AG Grid, Chart.js, SheetJS (로컬 번들)
│       ├── css/style.css      # 디자인 시스템 (사이드바, 카드, 배지, 룰 바 등)
│       └── js/app.js          # PV 네임스페이스: 그리드 초기화, 엑셀 export, 차트 팔레트/라벨
├── sample_data/
│   └── mock_companies/        # 가상 고객사 4곳 × 2개월 급여 목업 엑셀 (아래 참고)
├── scripts/
│   ├── generate_mock_payroll.py  # 목업 데이터 생성기
│   └── upload_mock_data.py       # 실제 업로드 API로 목업 데이터 일괄 전송
├── vercel.json                # Vercel Python 빌드 설정 (includeFiles로 static 포함)
└── run.py                     # 로컬 실행 진입점 (`python run.py`)
```

## 데이터 모델 핵심

- `PayrollUpload`: **client_name**(고객사명) + payroll_month + 업로드 메타. 전월 대비 비교는 반드시 같은 client_name 범위 안에서만 수행 (다른 고객사 데이터와 섞이지 않도록 수정된 부분)
- `PayrollRecord`: 업로드된 원본 급여 행 (사번/성명/조직/직급/기본급/수당/상여/공제/실지급액)
- `ValidationRule`: Rule 코드/이름/심각도/임계값/활성화 여부. 관리자가 `/rules`에서 활성화 토글·임계값 수정 가능
- `ValidationResult`: 건별 검증 결과 (심각도, 처리상태, Rule 참조)
- `ResolutionHistory`: 처리 상태 변경 이력 (처리자, 사유, 시각) — 향후 통계/ML 학습 라벨로 쓸 것을 염두에 두고 설계

## 검증 Rule 7종

| 코드 | 이름 | 심각도(내부값 → 화면 표기) | 설명 |
|---|---|---|---|
| RULE_001 | 사번 중복 | CRITICAL → 오류 | 동일 사번 2건 이상 |
| RULE_002 | 필수값 누락 | CRITICAL → 오류 | 사번/성명/조직/기본급/실지급액 중 누락 |
| RULE_003 | 음수 급여 | CRITICAL → 오류 | 기본급 < 0 |
| RULE_004 | 계산 불일치 | CRITICAL → 오류 | 기본급+수당+상여-공제 ≠ 실지급액 |
| RULE_005 | 전월 대비 급여 급증/급감 | WARNING → 경고 | 변동률 임계값(기본 ±30%, 조정 가능) 초과 |
| RULE_006 | 신규 입사자 | INFO → 참고 | 전월에 없던 사번 |
| RULE_007 | 퇴사자(전월 대비 누락) | INFO → 참고 | 전월에 있었는데 당월에 없음 |

`CRITICAL/WARNING/INFO`는 내부 로직·CSS 클래스명으로만 쓰고, 화면에는 전부 **오류/경고/참고**로
한글 표기 (`app/__init__.py`의 `severity_label()` Jinja 헬퍼 + `app.js`의 `PV.severityLabels`로 서버/클라 양쪽에서 통일).

## 인원 분류 기준 (오류 / 검토 필요 / 정상)

인원 단위, 중복 없이 집계 (`app/dashboard.py`의 `_upload_summary()`):

1. **오류** = 오류(CRITICAL) 항목이 하나라도 있는 인원
2. **검토 필요** = 오류는 없고 경고(WARNING) 항목만 있는 인원
3. **정상** = 그 외 전원 (참고 항목만 있어도 정상)

## 주요 화면 (사이드바 메뉴 순서)

1. **파일 업로드** — 고객사명 + 기준월 + 파일(xlsx/xls/csv). 선택 즉시 SheetJS로 클라이언트단 미리보기 표시
2. **월별 현황**(구 "대시보드") — "고객사별 최신 현황"(고객사 선택과 무관하게 항상 전체 표시) → 고객사 선택 탭 → 선택 고객사의 KPI/차트/최근 업로드
3. **조직별 현황**(구 "조직별 통계") — 고객사 선택 후 부서별 심각도 현황(라인 차트), 월별 오류 추이
4. **검증 이력** — 전체/고객사별 업로드 이력, 업무량 통계
5. **Rule 관리**(관리자 전용) — Rule 활성화/임계값 조정
6. 검증 상세 화면(업로드별) — AG Grid 결과 테이블(체크박스 다중 선택 → 처리 패널, 1건이면 단건 상세, 여러 건이면 일괄 처리), 오류 유형별 건수 비례 막대(심각도 색상), 엑셀 내보내기, 재검증, 삭제(관리자)

## 업로드 알림 (Slack)

`SLACK_WEBHOOK_URL` 환경변수를 설정하면, 업로드 검증이 끝난 직후 오류(CRITICAL) 또는 경고(WARNING)가
1건이라도 있을 때 Slack 채널로 알림을 보낸다 (`app/notify.py`). 설정하지 않으면 완전히 no-op —
담당자가 굳이 대시보드를 열어보지 않아도 오류 발생 여부를 알 수 있게 하기 위한 기능.

## BPO 다중 고객사 목업 데이터

`sample_data/mock_companies/`에 업종이 다른 가상 고객사 4곳, 2개월(2026-01/02)치:

- **세종물류** (물류, 36명) · **한빛전자** (제조, 52명) · **그린테이블푸드** (외식, 26명) · **파인트리소프트** (IT, 22명)
- 2월 데이터에는 7종 Rule이 모두 시연되도록 승진 인상, 신규 입사, 퇴사, 사번 중복, 필수값 누락,
  계산 불일치, 음수 급여를 의도적으로 포함
- 재생성: `python scripts/generate_mock_payroll.py`
- 실제 업로드: `python scripts/upload_mock_data.py --url <대상 서버 URL>`

## 보안 관련 이력 (중요)

- 초기에는 관리자 초기 비밀번호가 코드/로그인 화면에 하드코딩되어 있었음 (Public 저장소라 위험) → 수정 완료
- 현재는 `ADMIN_INITIAL_PASSWORD` 환경변수로 지정하거나, 없으면 최초 시드 시 무작위 생성 후 **서버 로그에만** 1회 출력
- 로그인한 사용자가 `/account/password`에서 직접 비밀번호 변경 가능
- 운영에 노출됐던 기존 비밀번호는 이미 새 값으로 교체함
- `.env`류 파일은 커밋 이력 전체를 검사했고 한 번도 커밋된 적 없음 (`.gitignore`에 `.env`, `.env.*` 포함)

## 알려진 제한사항 / 다음 단계 후보

- **재검증 제약**: `/uploads/<id>/revalidate`는 기존 검증 결과를 전부 삭제 후 재생성하므로, 이미 입력된 처리 상태/사유가 함께 사라짐. 사번+Rule 키로 기존 이력을 유지한 채 병합하는 방식으로 개선 필요
- **정리 스크립트 주의**: `Model.query.delete()` 같은 벌크 삭제는 SQLAlchemy cascade를 타지 않음. 반드시 `db.session.delete(instance)`(단건) 또는 자식 테이블부터 순서대로 명시적 삭제할 것 — 과거 이 문제로 로컬 DB에 검증 결과가 중복 집계된 적 있음
- **PRD 로드맵**: 이번 구현은 Phase 1(Rule-Based 검증)~Phase 2(이력 축적) 범위. Phase 3(업무량/패턴 분석 고도화), Phase 4(통계 기반 기준 자동 산출), Phase 5(ML 기반 오류 예측)는 미구현
- **고객사 필드 보강 여지**: 현재 `client_name`은 자유 텍스트 입력(datalist로 자동완성만 제공). 별도 Company 테이블로 정규화하면 오타 방지·고객사별 설정(예: Rule 임계값 커스터마이즈) 확장이 쉬워짐

## 로컬 실행

```bash
cd payroll-validator
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python run.py
# http://127.0.0.1:5000
```

## 배포 파이프라인 재현 방법 (새 환경/브랜치 등)

1. `git push origin master` → Vercel이 GitHub 연동을 통해 자동 빌드/배포
2. DB 스키마 변경 시 `app/__init__.py`의 `_run_light_migrations()`에 컬럼 추가 로직을 넣어두면
   앱 재기동 시 자동으로 `ALTER TABLE`이 실행됨 (별도 마이그레이션 툴 없음)
3. 프로덕션 환경변수는 `vercel env add <KEY> production` (Vercel CLI) 또는 대시보드에서 관리
