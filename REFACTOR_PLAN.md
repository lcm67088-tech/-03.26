# nplace.io 전체 리팩토링 계획

> 작성일: 2026-03-23  
> 기준 브랜치: main  
> 목적: 폴더 구조 정리, PM2 통합, 프론트 버그 수정, DB 모델 정합성 확보

---

## 📁 현재 구조 → 목표 구조

```
현재                                   목표
nplace-project/                        nplace-project/
├── frontend_html/          →          ├── frontend/
├── backend/                →          ├── backend/        (내부 점검)
├── parser/                 →          ├── parser/         (내부 점검)
├── ecosystem.config.cjs    →          ├── ecosystem.config.cjs  (통합)
├── parser_ecosystem.config.cjs  →     │   (위로 통합 후 삭제)
├── __pycache__/            →          │   (삭제)
├── _archive_internal/      →          ├── _archive_internal/
└── docs/                   →          └── docs/
```

---

## 🐛 확인된 버그 & 문제 목록

| # | 파일 | 문제 | 원인 | 해결 방안 | 상태 |
|---|------|------|------|-----------|------|
| F-1 | 모든 HTML | `app.js?v=` 수동 관리 | 빌드 시스템 없는 정적 서빙 | 보류 — 파일 해시 자동 주입 예정 | ⏳ 보류 |
| F-2 | `place-status.html` L941~ | 간트차트 달력형 아님 (수평 타임라인) | 요구사항 오해 | 7열 달력 그리드로 재작성 | ⏳ 대기 |
| F-3 | `dashboard.html` L211 | 최근 주문 테이블: 주문번호 컬럼 + 플레이스명이 상품 서브텍스트로 숨겨짐 | 컬럼 설계 미흡 | 플레이스명/상품명 분리 독립 컬럼, 주문번호 제거 | ⏳ 대기 |
| F-4 | `dashboard.html` L57,87,102,103 | `savedCount` 필드 mock 데이터 잔존 | 제거 작업 누락 | mock 데이터 4곳 삭제 | ⏳ 대기 |
| F-5 | `ecosystem.config.cjs` L7 | `cwd: frontend_html` 하드코딩 | 폴더명 변경 미반영 | 폴더 리네임 후 `frontend`로 수정 | ⏳ 대기 |
| F-6 | `backend/app/core/config.py` L33 | CORS `localhost:3000`만 허용 | 개발 설정 그대로 | 실 배포 시 도메인 추가 필요 (현재 개발 단계 OK) | 📝 문서화 |
| F-7 | `backend/requirements.txt` | `>=` 범위 지정, 버전 고정 없음 | 빌드 일관성 없음 | 실 배포 시 `pip freeze`로 고정 권장 | 📝 문서화 |
| F-8 | 프로젝트 루트 | `__pycache__` 루트에 생성 | parser 실행 위치 문제 | 삭제 + `.gitignore` 보강 | ⏳ 대기 |
| F-9 | 루트 | PM2 설정 파일 2개 분리 | frontend/parser 별도 설정 | 통합 후 삭제 | ⏳ 대기 |
| F-10 | `frontend_html/test-login.html` | 임시 테스트 파일 잔존 | 개발 중 생성 | 삭제 | ⏳ 대기 |
| DB-1 | Sprint7~9 모델 | `Base` 직접 상속 → `timezone=True` 불일치, 타임스탬프 수동 정의 | BaseModel 미상속 | `BaseModel` 상속으로 교체, 수동 id/created_at/updated_at 제거 | ⏳ 대기 |
| DB-2 | `user.py` | `notification_settings` back_populates 누락 | relationship 반대편 미정의 | `user.py`에 relation 추가 | ⏳ 대기 |
| DB-3 | `user.py` | `notifications` back_populates 누락 | relationship 반대편 미정의 | `user.py`에 relation 추가 | ⏳ 대기 |
| DB-4 | `workspace.py` | `notifications` back_populates 누락 | relationship 반대편 미정의 | `workspace.py`에 relation 추가 | ⏳ 대기 |
| DB-5 | `app.js` L515 vs DB ENUM | `refund_requested` 프론트 상태가 DB ENUM에 없음 | DB: `disputed`, 프론트: `refund_requested` 혼재 | `app.js` ORDER_STATUS를 DB 기준으로 정렬 | ⏳ 대기 |
| DB-6 | `keyword_rankings` 테이블 | 파티셔닝 미구현 | 데이터 급증 시 성능 위험 | 현재 데모 단계 → README에 TODO 기재 | 📝 문서화 |
| DB-7 | `requirements.txt` | `>=` 범위 지정 | 배포 환경 버전 불일치 위험 | 실 배포 전 `pip freeze`로 고정 | 📝 문서화 |
| DB-8 | `backend/app/core/config.py` | `.env` 없을 시 하드코딩 DB URL 사용 | default 값 존재 | `.env.example` 점검 및 문서화 | ⏳ 대기 |

---

## 📋 Phase별 작업 계획

---

### Phase 0 — 백업 & 스냅샷

| # | 작업 | 방법 | 상태 |
|---|------|------|------|
| 0-1 | 전체 프로젝트 tar.gz 백업 | `ProjectBackup` 툴 실행 | ⏳ 대기 |
| 0-2 | git pre-refactor 커밋 | `git add . && git commit -m "pre-refactor snapshot"` | ⏳ 대기 |

---

### Phase 1 — 폴더 구조 정리

| # | 작업 | 정확한 조작 | 상태 |
|---|------|-------------|------|
| 1-1 | `frontend_html` → `frontend` 리네임 | `mv frontend_html frontend` | ⏳ 대기 |
| 1-2 | 루트 `__pycache__` 삭제 | `rm -rf __pycache__` | ⏳ 대기 |
| 1-3 | `parser/__pycache__` 삭제 | `rm -rf parser/__pycache__` | ⏳ 대기 |
| 1-4 | `frontend/test-login.html` 삭제 | `rm frontend/test-login.html` | ⏳ 대기 |
| 1-5 | `.gitignore` 보강 | `**/__pycache__/`, `*.pyc`, `.env`, `*.log` 추가 | ⏳ 대기 |

---

### Phase 2 — PM2 설정 통합

| # | 작업 | 정확한 조작 | 상태 |
|---|------|-------------|------|
| 2-1 | `ecosystem.config.cjs` 수정 | `cwd: frontend_html` → `cwd: frontend` + parser 앱 항목 병합 | ⏳ 대기 |
| 2-2 | `parser_ecosystem.config.cjs` 삭제 | `rm parser_ecosystem.config.cjs` | ⏳ 대기 |
| 2-3 | PM2 재시작 & 검증 | `pm2 delete all && pm2 start ecosystem.config.cjs && pm2 list` → `nplace-demo`, `nplace-parser-api` 둘 다 `online` 확인 | ⏳ 대기 |

---

### Phase 3 — Frontend 수정

| # | 작업 | 파일 | 정확한 조작 | 상태 |
|---|------|------|-------------|------|
| 3-1 | 최근 주문 테이블 컬럼 수정 | `dashboard.html` L211 | `<th>주문번호</th><th>상품</th>` → `<th>플레이스명</th><th>상품명</th>` / 주문번호 `<td>` 삭제, 각 컬럼 독립 `<td>` | ⏳ 대기 |
| 3-2 | `savedCount` 제거 | `dashboard.html` L57,87,102,103 | `savedCount:xxxx` 4곳 삭제 | ⏳ 대기 |
| 3-3 | 간트차트 달력형 재작성 | `place-status.html` L941~ | `buildOrders()` 전체 교체 — 7열(일~토) 달력 그리드, 주 단위 행, 오늘 파란 원 강조, ◀▶ 월 이동 버튼 | ⏳ 대기 |
| 3-4 | `app.js` 버전 주석 업데이트 | `app.js` L4 | `updated: 2026-03-25` → `2026-03-23` | ⏳ 대기 |

---

### Phase 4 — DB 모델 리팩토링

| # | 작업 | 파일 | 정확한 조작 | 상태 |
|---|------|------|-------------|------|
| 4-1 | Sprint7~9 모델 `BaseModel` 상속 교체 | `subscription.py`, `settlement.py`, `notification.py`, `notification_setting.py` | `Base` → `BaseModel`, 수동 `id`/`created_at`/`updated_at` 제거 | ⏳ 대기 |
| 4-2 | `user.py` `notification_settings` relation 추가 | `user.py` | `notification_settings = relationship(...)` 추가 | ⏳ 대기 |
| 4-3 | `user.py` `notifications` relation 추가 | `user.py` | `notifications = relationship(...)` 추가 | ⏳ 대기 |
| 4-4 | `workspace.py` `notifications` relation 추가 | `workspace.py` | `notifications = relationship(...)` 추가 | ⏳ 대기 |
| 4-5 | `app.js` ORDER_STATUS DB 기준 동기화 | `app.js` L515~521 | `refund_requested` → DB ENUM 기준으로 정리 | ⏳ 대기 |
| 4-6 | `keyword_rankings` 파티셔닝 TODO 기재 | `README.md` | 향후 파티션 마이그레이션 필요 항목 기재 | ⏳ 대기 |
| 4-7 | `.env.example` 점검 | `.env.example` | DATABASE_URL, SECRET_KEY, CORS_ORIGINS 필수 항목 확인 | ⏳ 대기 |

---

### Phase 5 — 서비스 재시작 & 검증

| # | 작업 | 확인 방법 | 상태 |
|---|------|-----------|------|
| 5-1 | PM2 전체 재시작 | `pm2 delete all && pm2 start ecosystem.config.cjs` | ⏳ 대기 |
| 5-2 | 프론트엔드 포트 확인 | `curl http://localhost:3000` → 200 OK | ⏳ 대기 |
| 5-3 | 파서 API 헬스체크 | `curl http://localhost:8000/health` → `{"status":"ok"}` | ⏳ 대기 |
| 5-4 | 각 페이지 동작 확인 | dashboard (주문 테이블), place-status (달력 간트), orders | ⏳ 대기 |
| 5-5 | 최종 git 커밋 | `git add . && git commit -m "refactor: 전체 폴더/PM2/프론트/DB 리팩토링"` | ⏳ 대기 |

---

## 🚫 변경하지 않는 것

- `backend/` router, schema, service 비즈니스 로직
- `parser/naver_place_parser.py` 실행 로직
- `frontend/css/style.css` 테마 시스템
- `docs/` PRD 문서
- 캐시 버전 자동화 (보류)

---

## 📊 진행 현황

| Phase | 항목 수 | 완료 | 상태 |
|-------|---------|------|------|
| Phase 0 — 백업 | 2 | 0 | ⏳ |
| Phase 1 — 폴더 정리 | 5 | 0 | ⏳ |
| Phase 2 — PM2 통합 | 3 | 0 | ⏳ |
| Phase 3 — Frontend | 4 | 0 | ⏳ |
| Phase 4 — DB 모델 | 7 | 0 | ⏳ |
| Phase 5 — 검증 | 5 | 0 | ⏳ |
| **합계** | **26** | **0** | ⏳ |

---

*최종 업데이트: Phase 시작 전*
