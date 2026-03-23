# nplace.io — 프론트엔드 데모

네이버 플레이스 마케팅 최적화 SaaS 플랫폼의 프론트엔드 데모입니다.

---

## 🚀 빠른 시작

`index.html`을 브라우저에서 열거나, 로컬 서버를 실행하세요.

### 데모 계정

| 구분 | 이메일 | 비밀번호 |
|------|--------|----------|
| 일반 계정 | admin@nplace.io | password123 |
| 어드민 계정 | superadmin@nplace.io | admin1234! |

> 어드민 계정으로 로그인하면 자동으로 어드민 전용 메뉴가 표시됩니다.

---

## 📄 페이지 구성

| 파일 | 설명 | 접근 |
|------|------|------|
| `index.html` | 로그인 페이지 | 공개 |
| `dashboard.html` | 메인 대시보드 (KPI, 순위 트렌드, 최근 주문) | 로그인 필요 |
| `places.html` | 플레이스·키워드 관리 | 로그인 필요 |
| `orders.html` | 주문 관리 (카트 위자드, 엑셀 대량 등록) | 로그인 필요 |
| `billing.html` | 구독·결제·잔액 충전 | 로그인 필요 |
| `notifications.html` | 알림 센터 | 로그인 필요 |
| `upgrade.html` | 플랜 변경 | 로그인 필요 |
| `team.html` | 팀원 관리·초대 | 로그인 필요 |
| `account.html` | 계정 설정·비밀번호 변경 | 로그인 필요 |
| `admin.html` | 어드민 대시보드 | 어드민 전용 |
| `admin-media.html` | 매체사 관리 (리워드·블로그·영수증 설정) | 어드민 전용 |
| `monitor.html` | 순위 모니터링 실시간 대시보드 | 로그인 필요 |

---

## 🎨 테마

- 헤더 우측의 **☀️ / 🌙 버튼**으로 라이트/다크 모드 전환
- 선택한 테마는 `localStorage`에 저장되어 다음 방문 시 유지
- **라이트 모드**: 밝은 배경 + 어두운 사이드바 (가독성 최적화)
- **다크 모드**: 전체 다크 테마 (기본값)

---

## 🔑 인증 흐름

```
index.html (로그인)
    ↓ 일반 계정
dashboard.html → places.html → orders.html → billing.html
              → notifications.html → upgrade.html
              → team.html → account.html

    ↓ 어드민 계정
admin.html → orders.html → admin-media.html → team.html → billing.html
```

- 미로그인 상태에서 보호 페이지 접근 시 → `index.html` 리다이렉트
- 어드민 전용 페이지(`admin.html`) 일반 계정 접근 시 → `dashboard.html` 리다이렉트
- 어드민 계정은 모든 페이지에서 **어드민 전용 사이드바 메뉴** 표시

---

## 🗂️ 파일 구조

```
/
├── index.html              로그인
├── dashboard.html          대시보드
├── places.html             플레이스 관리
├── orders.html             주문 관리
├── billing.html            구독·결제
├── notifications.html      알림 센터
├── upgrade.html            플랜 변경
├── team.html               팀원 관리
├── account.html            계정 설정
├── admin.html              어드민 대시보드
├── css/
│   └── style.css           통합 스타일 (다크/라이트 테마)
├── js/
│   └── app.js              공통 JS (인증·라우팅·사이드바·테마·토스트)
└── README.md
```

---

## 🛠️ 기술 스택

- **HTML5 / CSS3 / Vanilla JS** — 외부 프레임워크 없음
- **Pretendard** — 한국어 최적화 폰트 (jsDelivr CDN)
- **Chart.js** — 순위 트렌드 차트
- **SheetJS (XLSX)** — 주문 엑셀 대량 등록/내보내기

---

## ✅ 구현 완료 기능

- [x] 다크/라이트 테마 토글 (localStorage 저장)
- [x] 로그인/로그아웃 (localStorage 세션)
- [x] 일반/어드민 계정 분기 로그인
- [x] 전 페이지 사이드바 네비게이션 연결
- [x] 어드민 계정 → 어드민 전용 메뉴 자동 표시
- [x] 사이드바 접기/펼치기
- [x] 헤더 알림 드롭다운 / 유저 메뉴 드롭다운
- [x] 대시보드 KPI 카드 + 순위 트렌드 차트
- [x] 플레이스/키워드 관리 (추가·삭제·선택)
- [x] 주문 위자드 (카테고리→브랜드→카트→결제)
- [x] 엑셀 대량 주문 등록 (SheetJS)
- [x] 구독·결제·잔액 충전 페이지
- [x] 알림 센터 (탭·읽음 처리)
- [x] 팀원 관리·초대 페이지
- [x] 계정 설정 (프로필·비밀번호·알림)
- [x] 플랜 변경 페이지
- [x] 어드민 대시보드 (KPI·유저·주문 현황)

## 🔲 미구현 (백엔드 연동 필요)

- [ ] 실제 API 연동 (현재 Mock 데이터)
- [ ] 이메일 회원가입/비밀번호 찾기
- [ ] 소셜 로그인 (카카오·Google)
- [ ] 실제 결제 연동 (PG사)
- [ ] 팀원 초대 이메일 발송
- [ ] 실시간 크롤링 순위 데이터

---

## 🕷️ 백엔드 크롤러 (Sprint 9)

### 파일 구조

```
backend/
├── crawl_test.py               ← 단독 실행 테스트 스크립트 (★)
├── requirements.txt
├── workers/
│   ├── celery_app.py           Beat 스케줄 (일 4회 순위, 새벽 1회 정보 갱신)
│   ├── tasks/
│   │   ├── crawl.py            run_rank_check / crawl_place_info Celery 태스크
│   │   └── scheduler.py        daily_rank_check / refresh_all_place_info
│   └── crawler/
│       ├── stealth.py          봇 탐지 우회 (webdriver 제거, UA 로테이션, 인간형 딜레이)
│       ├── parsers.py          DOM 파서 (순위 체크 + 플레이스 기본 정보)
│       ├── rank_checker.py     키워드 순위 체크 오케스트레이터
│       └── place_info.py       플레이스 기본 정보 수집기
└── app/utils/naver.py          URL 파싱 유틸리티
```

### 수집 항목

| 항목 | 수집 여부 | 파서 위치 |
|------|-----------|----------|
| 상호명 / 카테고리 | ✅ | `_parse_name_category` |
| 주소 / 전화번호 / 홈페이지 | ✅ | `_parse_contact` |
| 영업시간 (요일별) / 브레이크 / 라스트오더 | ✅ | `_parse_hours` |
| 방문자 리뷰 수 / 평점 | ✅ | `_parse_reviews` |
| 블로그 리뷰 수 / 저장 수 | ✅ | `_parse_reviews` |
| 월 방문자 수 | ✅ | `_parse_visitor_monthly` |
| 메뉴 목록 (이름 + 가격) | ✅ | `_parse_menus` |
| 사진 수 | ✅ | `_parse_photos` |
| 파워링크 / 플레이스 광고 노출 | ✅ | `_parse_ads` |
| 키워드 순위 (최대 100위) | ✅ | `rank_checker.py` |

### 크롤러 단독 테스트

```bash
# 1. 의존성 설치
cd backend
pip install -r requirements.txt
playwright install chromium

# 2. URL 파싱만 테스트 (Playwright 불필요)
python crawl_test.py

# 3. 스텔스 브라우저 접속 확인
python crawl_test.py --stealth

# 4. 플레이스 기본 정보 수집 (실제 크롤링)
python crawl_test.py --place 1005166855
python crawl_test.py --place "https://m.place.naver.com/restaurant/19797085"

# 5. 키워드 순위 체크
python crawl_test.py --keyword "강남 맛집" --mid 1005166855

# 6. 전체 테스트 + JSON 저장
python crawl_test.py --full --out result.json

# 7. 프록시 사용 (IP 차단 우회)
python crawl_test.py --place 1005166855 --proxy http://127.0.0.1:8888
```

### 봇 탐지 우회 전략

| 기법 | 구현 |
|------|------|
| `navigator.webdriver` 제거 | `stealth.py` init_script |
| Chrome 120+ 실제 UA 랜덤 | `fake-useragent` |
| 인간형 마우스/스크롤 딜레이 | `human_delay()`, `human_scroll()` |
| 이미지/폰트/미디어 차단 | 리소스 필터링 (속도 3~5배 향상) |
| 20회마다 세션 초기화 | `RESET_EVERY = 20` |
| 봇 차단 감지 → 30분 쿨다운 후 재시도 | `is_bot_blocked()` |

### Beat 스케줄 (KST)

| 시각 | 태스크 |
|------|--------|
| 03:00 | `refresh_all_place_info` — 플레이스 기본 정보 전체 갱신 |
| 06:00 | `daily_rank_check` — 순위 체크 1차 |
| 10:00 | `daily_rank_check` — 순위 체크 2차 |
| 14:00 | `daily_rank_check` — 순위 체크 3차 |
| 20:00 | `daily_rank_check` — 순위 체크 4차 |

---

---

## 🔧 Sprint 9 — 어드민 심화 (2026-03-20)

### 신규 백엔드 파일

| 파일 | 설명 |
|------|------|
| `backend/app/models/settlement.py` | Settlement / SettlementItem ORM 모델 |
| `backend/app/models/__init__.py` | Settlement, SettlementItem import 추가 |
| `backend/app/models/media_company.py` | settlements 관계(back_populates) 추가 |
| `backend/alembic/versions/006_add_settlements.py` | settlements / settlement_items 테이블 마이그레이션 |
| `backend/app/schemas/admin_advanced.py` | 유저·워크스페이스·정산·통계 전용 Pydantic 스키마 |
| `backend/app/routers/admin_users.py` | 유저 관리 라우터 (6 엔드포인트) |
| `backend/app/routers/admin_workspaces.py` | 워크스페이스 관리 라우터 (5 엔드포인트) |
| `backend/app/routers/admin_settlements.py` | 정산 관리 라우터 (6 엔드포인트) |
| `backend/app/routers/admin_stats.py` | 통계 라우터 (3 엔드포인트) |
| `backend/app/main.py` | Sprint 9 라우터 4개 등록 |

### 새 API 엔드포인트 요약

#### 유저 관리 (`/api/v1/admin/users`)
| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/admin/users` | 유저 목록 (검색·필터·페이지) | admin+ |
| GET | `/admin/users/{id}` | 유저 상세 | admin+ |
| PATCH | `/admin/users/{id}/role` | 역할 변경 | superadmin |
| PATCH | `/admin/users/{id}/status` | 활성/비활성 | admin+ |
| POST | `/admin/users/{id}/force-logout` | 강제 로그아웃 | admin+ |
| GET | `/admin/users/export/csv` | CSV 내보내기 | admin+ |

#### 워크스페이스 관리 (`/api/v1/admin/workspaces`)
| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/admin/workspaces` | 목록 (검색·필터·페이지) | admin+ |
| GET | `/admin/workspaces/{id}` | 상세 (멤버·플레이스·빌링) | admin+ |
| PATCH | `/admin/workspaces/{id}/plan` | 플랜 강제 변경 | admin+ |
| POST | `/admin/workspaces/{id}/deactivate` | 소프트 삭제 | admin+ |
| GET | `/admin/workspaces/export/csv` | CSV 내보내기 | admin+ |

#### 정산 관리 (`/api/v1/admin/settlements`)
| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/admin/settlements` | 정산 목록 (필터·페이지) | admin+ |
| GET | `/admin/settlements/{id}` | 정산 상세 + 항목 | admin+ |
| POST | `/admin/settlements/generate` | 정산 생성 (completed 주문 집계) | admin+ |
| POST | `/admin/settlements/{id}/approve` | 승인 (pending→approved) | admin+ |
| POST | `/admin/settlements/{id}/pay` | 지급 (approved→paid) | admin+ |
| GET | `/admin/settlements/export/csv` | CSV 내보내기 | admin+ |

#### 통계 (`/api/v1/admin/stats`)
| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/admin/stats/overview` | KPI 통계 (MRR, ARR, 신규 유저 등) | admin+ |
| GET | `/admin/stats/revenue` | 월별 매출 통계 (최근 N개월) | admin+ |
| GET | `/admin/stats/export/csv` | 통계 CSV 내보내기 | admin+ |

### 신규 프론트엔드 파일

| 파일 | 설명 |
|------|------|
| `frontend/hooks/useAdminAdvanced.ts` | 유저·워크스페이스·정산·통계 TanStack Query 훅 |
| `frontend/app/(admin)/admin/users/page.tsx` | 유저 목록 페이지 |
| `frontend/app/(admin)/admin/users/[userId]/page.tsx` | 유저 상세 페이지 |
| `frontend/app/(admin)/admin/workspaces/page.tsx` | 워크스페이스 목록 페이지 |
| `frontend/app/(admin)/admin/workspaces/[workspaceId]/page.tsx` | 워크스페이스 상세 페이지 |
| `frontend/app/(admin)/admin/settlements/page.tsx` | 정산 관리 페이지 |
| `frontend/app/(admin)/admin/stats/page.tsx` | 통계 대시보드 (Recharts AreaChart/PieChart) |
| `frontend/components/admin/ForceChangePlanModal.tsx` | 플랜 강제 변경 모달 |

### 데이터 모델 (Sprint 9 신규)

```
settlements
  id               UUID PK
  media_company_id UUID FK → media_companies.id
  month            VARCHAR(7)   "YYYY-MM"
  status           VARCHAR(20)  pending | approved | paid
  total_orders     INTEGER
  total_amount     INTEGER
  commission_rate  FLOAT
  commission_amount INTEGER     = round(total_amount * commission_rate)
  approved_at      TIMESTAMP NULL
  paid_at          TIMESTAMP NULL
  created_at / updated_at TIMESTAMP

settlement_items
  id               UUID PK
  settlement_id    UUID FK → settlements.id
  order_id         UUID FK → orders.id  (unique)
  amount           INTEGER
  commission_amount INTEGER
  created_at       TIMESTAMP
```

### 다음 단계 (Sprint 11 권장)

- [ ] CS 관리 (지원 티켓 시스템)
- [ ] 보안 대시보드 (로그인 실패 패턴, IP 블랙리스트)
- [ ] 정산 알림 (미디어사 이메일 발송)
- [ ] 어드민 감사 로그 (누가 무엇을 변경했는지 추적)
- [ ] 벌크 작업 (여러 워크스페이스 동시 플랜 변경)

---

## 🔧 Sprint 10 — 매체사 상품 설정 심화 (2026-03-20)

### 신규 / 수정 파일

| 파일 | 변경 | 설명 |
|------|------|------|
| `admin-media.html` | 신규 | 매체사 관리 전용 어드민 페이지 |
| `orders.html` | 수정 | 주문 위저드에 브랜드 설정 정보 패널 추가 |
| `js/app.js` | 수정 | ADMIN_MENU 매체사 관리 링크 업데이트 |

### admin-media.html 기능 상세

#### 레이아웃
- **좌 패널**: 매체사 목록 (검색, 활성/비활성 필터, KPI 카드 4개)
- **우 패널**: 선택된 매체사 상세 탭 패널 (4개 탭)

#### 탭 1: 🎁 리워드 설정
- 카테고리별(블로그/영수증/트래픽/저장/SNS) **최소 주문 수량** 설정
- **일키 전용** 토글 (ON: 해당 상품은 일 수량 입력 필수)
- **수수료율(%)** 설정 (정산금액 = 주문금액 × 수수료율)

#### 탭 2: 📝 블로그 리뷰 설정
- 브랜드별 **글자수 범위** (최소~최대)
- 브랜드별 **사진 수 범위** (최소~최대)
- **사진 크롤링** 활성화/비활성화 토글
- **레퍼런스 링크** 관리 (기본 접힘 → 펼쳐서 URL/설명 확인)
  - 링크 추가/삭제
  - 제목, URL, 설명 편집

#### 탭 3: 🧾 영수증 리뷰 설정
- **포토 첨부** 여부 (필수/선택) 토글
- **주말 발행** 허용/금지 토글
- **발행 금지 날짜** 등록 (날짜 선택 → 태그 추가, 태그 X 버튼으로 삭제)
- **발행 원고** 텍스트 에디터 (변수 삽입 버튼: 업체명, 주소, 해시태그 등)
- 문자 수 카운터

#### 탭 4: 🏢 기본 정보
- 매체사 기본 정보 조회 (이름, 이메일, 전화, 계좌, 수수료율, 통계)
- 설정 요약 카드 (리워드/블로그/영수증 설정 수)

### orders.html 변경 사항

#### 주문 위저드 Step2 확장
- **일키 전용 경고 배지**: 일키 전용 상품 선택 시 노란 경고 뱃지 표시
- **최소 수량 안내 배지**: 최소 주문 수량 cyan 배지 표시
- **블로그 리뷰 가이드 패널** (기본 접힘 → 펼쳐서 확인):
  - 최소/최대 글자수, 최소/최대 사진수 카드
  - 사진 크롤링 활성화 여부
  - 레퍼런스 링크 목록 (각각 접기/펼치기)
- **영수증 리뷰 가이드 패널** (기본 접힘 → 펼쳐서 확인):
  - 포토 필수 여부, 주말 발행 허용 여부 배지
  - 발행 금지 날짜 목록
  - 발행 원고 텍스트 표시

#### 주문 상세 모달 확장
- 블로그/영수증 카테고리 주문에 설정 요약 정보 표시
  - 블로그: 글자수/사진수/크롤링 여부
  - 영수증: 포토/주말/금지날짜 요약

#### 주문 검증 강화
- **일키 전용** 상품: 일 수량 미입력 시 오류 토스트
- **최소 수량** 미달 시 오류 토스트 (해당 브랜드 이름 포함)

### 데이터 구조 (Mock — 향후 API 연동)

```javascript
BRAND_SETTINGS = {
  blog: {
    [brandId]: {
      minChars, maxChars,         // 글자수 범위
      minPhotos, maxPhotos,       // 사진수 범위
      photoCrawl,                 // 사진 크롤링 여부
      refs: [{ title, url, desc }] // 레퍼런스 링크
    }
  },
  receipt: {
    [brandId]: {
      hasPhoto,                   // 포토 첨부 필수 여부
      allowWeekend,               // 주말 발행 허용 여부
      blockedDates: [],           // 발행 금지 날짜 배열
      draft,                      // 발행 원고 텍스트
    }
  },
  rewardMinQty: {
    [category]: { [brandId]: number }  // 최소 주문 수량
  },
  dailyOnly: {
    [category]: { [brandId]: boolean } // 일키 전용 여부
  }
}
```

---

*최종 업데이트: 2026-03-20 (Sprint 10 매체사 상품 설정 심화)*

---

## 🔧 기술 부채 & TODO (DB/인프라)

### keyword_rankings 테이블 파티셔닝 (우선순위: 중)

> **현재 상태**: 단일 테이블에 전체 랭킹 이력 누적  
> **위험**: 키워드×장소×일별 데이터가 급증 시 쿼리 성능 저하

**권장 파티셔닝 전략 (PostgreSQL Range Partitioning)**:

```sql
-- 월별 Range 파티셔닝 (예시)
ALTER TABLE keyword_rankings PARTITION BY RANGE (created_at);

CREATE TABLE keyword_rankings_2026_03
  PARTITION OF keyword_rankings
  FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE keyword_rankings_2026_04
  PARTITION OF keyword_rankings
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
```

**마이그레이션 절차 (실 서비스 전 필요)**:
1. 새 파티션 테이블 생성 → 기존 데이터 COPY → 원본 RENAME
2. 월 단위 자동 파티션 생성 스크립트 추가 (cron 또는 pg_partman)
3. 인덱스 재생성: `(place_id, keyword_id, created_at)` 복합 인덱스

**참고**: 현재 데모/개발 단계에서는 파티셔닝 불필요. 월간 조회 수 100만 행 초과 시 적용 권장.

---

### requirements.txt 버전 고정 (우선순위: 배포 전 필수)

> **현재 상태**: `>=` 범위 지정으로 환경별 버전 불일치 위험

**조치 방법 (배포 환경 확정 후)**:
```bash
# 가상환경 활성화 후
pip install -r requirements.txt
pip freeze > requirements.lock.txt
# requirements.lock.txt를 배포 환경에서 사용
```

*최종 업데이트: 2026-03-23 (Phase 4 DB 리팩토링)*
