# nplace.io 프로젝트 컨텍스트

> **생성 시점**: Sprint 7 완료 (2026-03-19)
> **목적**: 새 채팅 세션에서 이 파일을 붙여넣어 Sprint 8+를 이어서 진행하기 위한 컨텍스트 스냅샷

---

## 프로젝트 개요

**nplace.io** – 네이버 플레이스 순위 관리 SaaS B2B 플랫폼

- 사업주가 자신의 네이버 플레이스 업체의 키워드 순위를 모니터링하고, 마케팅 서비스(블로그 리뷰 등)를 주문하는 서비스
- 멀티 워크스페이스, 플랜 기반 구독(Free/Starter/Pro/Enterprise)

---

## 기술 스택

### Backend
- **FastAPI** (Python 3.12) + **SQLAlchemy 2.0** (sync ORM)
- **PostgreSQL 16** (메인 DB), **Redis 7** (토큰 캐시 + 크롤링 카운터)
- **Alembic** (마이그레이션), **passlib[bcrypt]** (비밀번호), **python-jose** (JWT)
- **Pydantic v2** (스키마 검증)
- **Celery 5.3+** (비동기 크롤링 워커), **Celery Beat** (일일 스케줄러)

### Frontend
- **Next.js 14** (App Router, TypeScript)
- **Tailwind CSS v3**, **shadcn/ui** 컴포넌트
- **Zustand** (전역 상태), **TanStack Query v5** (서버 상태)
- **React Hook Form + Zod** (폼 검증)
- **Recharts** (순위 트렌드 차트)
- **axios** (HTTP), **sonner** (toast), **lucide-react** (아이콘)
- **date-fns** (날짜 유틸), **Pretendard** (폰트)
- 다크 테마: `bg-brand-dark` (#0a0a0f), 포인트 색상: `#00d4ff`

### 인프라
- **Docker Compose** (postgres, redis, backend, frontend, celery_worker, celery_beat)
- 포트: backend 8000, frontend 3000

---

## 전체 파일 구조 및 완성 상태

```
/
├── docker-compose.yml         ✅ Celery worker/beat 포함 완성
├── docker-compose.dev.yml     ✅ 완성
├── .env.example               ✅ 완성
├── CONTEXT.md                 ✅ Sprint 7 기준 업데이트
│
├── backend/
│   ├── Dockerfile             ✅
│   ├── requirements.txt       ✅ celery[redis]>=5.3.0 추가
│   ├── alembic/
│   │   └── versions/
│   │       ├── 001_initial.py              ✅ 초기 8개 테이블
│   │       ├── 002_add_crawl_jobs.py       ✅ [Sprint 4] crawl_jobs 테이블
│   │       ├── 003_add_products.py         ✅ [Sprint 5] product_types/products + orders 컬럼
│   │       ├── 004_add_notifications.py    ✅ [Sprint 7] notifications + notification_settings
│   │       └── 005_add_billing.py          ✅ [Sprint 8] subscriptions + billing_histories + workspaces.payment_method
│   ├── workers/               ✅ [Sprint 4]
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   └── tasks/
│   │       ├── __init__.py
│   │       ├── crawl.py
│   │       └── scheduler.py
│   └── app/
│       ├── main.py            ✅ [Sprint 8 업데이트] billing 라우터 등록 (모든 라우터 등록 완료)
│       ├── core/
│       │   ├── config.py      ✅
│       │   ├── database.py    ✅
│       │   ├── security.py    ✅
│       │   ├── redis.py       ✅
│       │   ├── dependencies.py ✅
│       │   └── constants.py   ✅
│       ├── models/
│       │   ├── base.py        ✅
│       │   ├── user.py        ✅
│       │   ├── workspace.py   ✅
│       │   ├── place.py       ✅
│       │   ├── keyword.py     ✅
│       │   ├── crawl_job.py   ✅
│       │   ├── media_company.py ✅
│       │   ├── order.py       ✅
│       │   ├── notification.py         ✅ [Sprint 7 신규] NotificationType enum (25종) + Notification 모델
│       │   ├── notification_setting.py ✅ [Sprint 7 신규] NotificationSetting 모델
│       │   └── __init__.py    ✅ [Sprint 7 업데이트] Notification, NotificationSetting, NotificationType 임포트
│       ├── schemas/
│       │   ├── common.py      ✅
│       │   ├── auth.py        ✅
│       │   ├── user.py        ✅
│       │   ├── workspace.py   ✅
│       │   ├── place.py       ✅
│       │   ├── keyword.py     ✅
│       │   ├── order.py       ✅
│       │   ├── admin.py       ✅
│       │   └── notification.py ✅ [Sprint 7 신규] NotificationResponse, NotificationListResponse, UnreadCountResponse, NotificationSettingResponse, BulkUpdateSettingsRequest 등
│       │   billing.py      ✅ [Sprint 8 신규] SubscriptionResponse, BillingHistoryResponse, PlanUpgradeRequest/Response, CancelSubscriptionRequest 등
│       ├── routers/
│       │   ├── auth.py               ✅
│       │   ├── workspaces.py         ✅
│       │   ├── places.py             ✅
│       │   ├── keywords.py           ✅
│       │   ├── orders.py             ✅ [Sprint 7 업데이트] 알림 서비스 호출 삽입
│       │   ├── admin.py              ✅ [Sprint 7 업데이트] 알림 서비스 호출 삽입
│       │   ├── notifications.py      ✅ [Sprint 7 신규] 7 엔드포인트
│       │   ├── account.py            ✅ [Sprint 7 신규] 5 엔드포인트
│       │   ├── workspace_members.py  ✅ [Sprint 7 신규] 4 엔드포인트
│       │   └── billing.py            ✅ [Sprint 8 신규] 7 엔드포인트
│       ├── services/
│       │   └── notification_service.py ✅ [Sprint 7 신규] send_notification(), get_user_notification_settings()
│       └── utils/
│           ├── __init__.py    ✅
│           ├── naver.py       ✅
│           └── seed.py        ✅
│
└── frontend/
    ├── Dockerfile             ✅
    ├── package.json           ✅
    ├── next.config.ts         ✅
    ├── tailwind.config.ts     ✅
    ├── middleware.ts          ✅
    ├── types/
    │   └── index.ts           ✅
    ├── store/
    │   └── authStore.ts       ✅
    ├── hooks/
    │   ├── useAuth.ts         ✅
    │   ├── useToast.ts        ✅
    │   ├── usePlaces.ts       ✅
    │   ├── useKeywords.ts     ✅
    │   ├── useOrders.ts       ✅
    │   ├── useAdmin.ts        ✅
    │   ├── useNotifications.ts ✅ [Sprint 7 신규] 8 훅 (useNotifications, useUnreadCount, useMarkNotificationRead, useMarkAllRead, useDeleteNotification, useNotificationSettings, useUpdateNotificationSettings, useBulkUpdateSettings)
    │   └── useAccount.ts      ✅ [Sprint 7 신규] 8 훅 (useMyProfile, useUpdateProfile, useChangePassword, useDeleteAccount, useWorkspaceMembers, useInviteMember, useUpdateMemberRole, useRemoveMember, useTransferOwnership)
│   useBilling.ts          ✅ [Sprint 8 신규] 7 훅 (useSubscription, useBillingHistory, useUpgradePlan, useDowngradePlan, useCancelSubscription, usePaymentMethod, useUpdatePaymentMethod) + 플랜 상수
    ├── lib/
    │   ├── api.ts             ✅
    │   ├── auth.ts            ✅
    │   └── utils.ts           ✅
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.tsx    ✅ [Sprint 8 확인] /billing 메뉴 (구독·결제, CreditCard 아이콘) 이미 포함
    │   │   ├── Header.tsx     ✅ [Sprint 7 업데이트] NotificationBell 컴포넌트 통합, useAuth 연동, 플랜 뱃지, 알림설정 링크
    │   │   └── PageHeader.tsx ✅
    │   ├── common/
    │   │   ├── StatusBadge.tsx   ✅
    │   │   ├── EmptyState.tsx    ✅
    │   │   └── LoadingSpinner.tsx ✅
    │   ├── notifications/
    │   │   ├── NotificationBell.tsx ✅ [Sprint 7 신규] 헤더 벨 아이콘 + 드롭다운 패널 (최근 10개, 전체읽음, 알림센터 이동)
    │   │   └── NotificationItem.tsx ✅ [Sprint 7 신규] 단일 알림 렌더링 (타입별 아이콘/색상, 읽음/삭제 액션)
    │   ├── places/            ✅
    │   ├── orders/            ✅
    │   ├── keywords/          ✅
    │   ├── rankings/          ✅
    │   └── admin/             ✅
    └── app/
        ├── globals.css        ✅
        ├── layout.tsx         ✅
        ├── providers.tsx      ✅
        ├── page.tsx           ✅
        ├── (auth)/            ✅ login / signup / forgot-password / reset-password
        ├── (dashboard)/
        │   ├── layout.tsx     ✅
        │   ├── dashboard/page.tsx  ✅
        │   ├── places/             ✅ 목록 / 등록 / [id] 상세
        │   ├── orders/             ✅ 목록 / 생성 / [id] 상세
        │   ├── notifications/
        │   │   ├── page.tsx        ✅ [Sprint 7 신규] 알림 센터 (탭 필터, 페이지네이션, 전체읽음)
        │   │   └── settings/
        │   │       └── page.tsx    ✅ [Sprint 7 신규] 알림 설정 (카테고리별 토글, 일괄저장)
        │   ├── account/
        │   │   └── page.tsx        ✅ [Sprint 7 신규] 내 계정 (프로필 수정, 비밀번호 변경, 회원탈퇴)
        │   ├── billing/
        │   │   ├── page.tsx        ✅ [Sprint 8 신규] 구독·결제 현황 (플랜 상태, 사용량 프로그레스바, 결제수단, 내역 테이블)
        │   │   └── upgrade/
        │   │       └── page.tsx    ✅ [Sprint 8 신규] 플랜 변경 (4개 플랜 카드, 월간/연간 20% 할인 토글, 업/다운그레이드 분기)
        │   └── workspaces/
        │       └── [id]/
        │           └── members/
        │               └── page.tsx ✅ [Sprint 7 신규] 멤버 관리 (목록, 초대, 역할변경, 제거, 소유권이전)
        └── (admin)/
            ├── layout.tsx          ✅
            └── admin/
                ├── page.tsx        ✅
                ├── orders/         ✅ 목록 / [id] 상세
                └── media-companies/ ✅
```

---

## Sprint별 완료 내역

### ✅ Sprint 1 – 기반 설정
- Docker Compose (postgres, redis, backend, frontend)
- SQLAlchemy 모델 8개 정의
- Next.js 14 프로젝트 설정 (Tailwind, shadcn/ui, 폰트)
- 레이아웃·공통 컴포넌트

### ✅ Sprint 2 – 인증 시스템
- `app/routers/auth.py` – 7 엔드포인트
- JWT + bcrypt + Redis refresh 토큰
- 4개 인증 페이지, axios 401 자동 갱신

### ✅ Sprint 3 – 대시보드 + 장소 관리
- `app/routers/places.py` – 6 엔드포인트
- `app/routers/workspaces.py`, `admin.py` 완성
- 장소 목록/등록/수정/삭제, 대시보드 요약
- 프론트: usePlaces 6훅, PlaceCard, 페이지 4개

### ✅ Sprint 4 – 키워드 관리 + 순위 크롤링 + 차트
**Backend**
- `app/models/crawl_job.py` – CrawlJob 모델
- `app/schemas/keyword.py` – 8개 스키마
- `app/routers/keywords.py` – 6 엔드포인트
- `workers/` – Celery 설정, Beat 스케줄, run_rank_check (Mock)
- `alembic/versions/002_add_crawl_jobs.py`

**Frontend**
- `hooks/useKeywords.ts` – 7개 훅
- `components/keywords/KeywordTable.tsx`, `AddKeywordModal.tsx`
- `components/rankings/RankingChart.tsx` – Recharts
- `app/(dashboard)/places/[id]/page.tsx` – 키워드+순위현황 탭

### ✅ Sprint 5 – 상품·주문 시스템
**Backend**
- `app/models/product.py`, `order.py` 확장
- `alembic/versions/003_add_products.py`
- `app/utils/seed.py` – 7개 상품 시드
- `app/routers/orders.py` – products(1) + orders(5) + payments(1)

**Frontend**
- `hooks/useOrders.ts` – 7 훅
- `components/orders/` – OrderStatusTimeline, RefundModal
- `app/(dashboard)/orders/` – 목록 / 생성 3단계 위저드 / 상세

### ✅ Sprint 6 – 어드민 주문·미디어사 관리
**Backend**
- `app/schemas/admin.py` – 10개 스키마
- `app/routers/admin.py` – /dashboard 유지 + 11 엔드포인트
  - 상태 전이 검증, admin_notes 누적, assigned 시 confirmed→in_progress 자동
  - Mock 알림: `print("[알림 mock] ...")`

**Frontend**
- `hooks/useAdmin.ts` – 12 훅
- `components/admin/` – AssignModal, CompleteOrderModal, RefundDecisionModal
- `app/(admin)/` – 레이아웃 + 대시보드 + 주문관리 + 매체사관리

### ✅ Sprint 7 – 알림 시스템 + 계정·멤버 관리
**Backend**
- `app/models/notification.py` – `NotificationType` enum 25종 + `Notification` 모델
- `app/models/notification_setting.py` – `NotificationSetting` 모델
- `app/models/__init__.py` – 신규 모델 임포트
- `app/schemas/notification.py` – 6개 스키마 (Response, ListResponse, UnreadCountResponse, SettingResponse, BulkUpdateRequest 등)
- `app/services/notification_service.py` – `send_notification()`, `get_user_notification_settings()`
- `app/routers/notifications.py` – 7 엔드포인트
  - `GET /api/v1/notifications` – 목록 (is_read 필터, 페이지네이션)
  - `GET /api/v1/notifications/unread-count` – 미읽음 수
  - `POST /api/v1/notifications/{id}/read` – 단건 읽음 처리
  - `POST /api/v1/notifications/read-all` – 전체 읽음
  - `DELETE /api/v1/notifications/{id}` – 단건 삭제
  - `GET /api/v1/notifications/settings` – 알림 설정 조회
  - `PUT /api/v1/notifications/settings` – 알림 설정 일괄 저장
- `app/routers/account.py` – 5 엔드포인트
  - `GET /api/v1/account/me` – 내 프로필
  - `PUT /api/v1/account/me` – 프로필 수정 (이름/전화)
  - `POST /api/v1/account/change-password` – 비밀번호 변경
  - `DELETE /api/v1/account/me` – 회원 탈퇴 (소프트)
  - `GET /api/v1/account/activity` – 최근 활동 요약
- `app/routers/workspace_members.py` – 4 엔드포인트
  - `GET /api/v1/workspaces/{id}/members` – 멤버 목록
  - `POST /api/v1/workspaces/{id}/members/invite` – 멤버 초대
  - `PATCH /api/v1/workspaces/{id}/members/{user_id}` – 역할 변경
  - `DELETE /api/v1/workspaces/{id}/members/{user_id}` – 멤버 제거
  - `POST /api/v1/workspaces/{id}/transfer-ownership` – 소유권 이전
- `app/routers/orders.py` – 알림 서비스 호출 삽입 (주문생성/취소/환불요청)
- `app/routers/admin.py` – 알림 서비스 호출 삽입 (주문완료/환불결정)
- `alembic/versions/004_add_notifications.py` – notifications + notification_settings 테이블
- `app/main.py` – 3개 신규 라우터 등록

**Frontend**
- `hooks/useNotifications.ts` – 8 훅 + NotificationType 상수 (NOTIFICATION_TYPE_LABELS, NOTIFICATION_TYPE_COLOR)
- `hooks/useAccount.ts` – 8 훅 (프로필/비밀번호/탈퇴 + 멤버 관리 CRUD)
- `components/notifications/NotificationBell.tsx` – 헤더 벨 아이콘 + 드롭다운 패널
- `components/notifications/NotificationItem.tsx` – 단일 알림 렌더링
- `components/layout/Header.tsx` – NotificationBell 통합, useAuth 연동, 플랜 뱃지
- `app/(dashboard)/notifications/page.tsx` – 알림 센터 (탭 필터, 20개 페이지네이션)
- `app/(dashboard)/notifications/settings/page.tsx` – 알림 설정 (카테고리별 채널 토글)
- `app/(dashboard)/account/page.tsx` – 내 계정 (프로필 수정, 비밀번호 변경, 회원탈퇴)
- `app/(dashboard)/workspaces/[id]/members/page.tsx` – 멤버 관리 (초대/역할변경/제거/소유권이전)

### ✅ Sprint 8 – 구독·결제 (Billing + Plan Management)
**Backend**
- `app/models/subscription.py` – `Subscription` + `BillingHistory` 모델
- `app/models/__init__.py` – Subscription, BillingHistory 임포트 추가
- `app/core/constants.py` – `PLAN_PRICES`, `PLAN_ORDER`, `get_plan_rank()` 추가
- `app/schemas/billing.py` – SubscriptionResponse, SubscriptionWithLimitsResponse, BillingHistoryResponse, PlanUpgradeRequest/Response, CancelSubscriptionRequest, PaymentMethodRequest/Response
- `app/routers/billing.py` – 7 엔드포인트 (subscription/history/upgrade/downgrade/cancel/payment-method GET·POST)
- `app/models/workspace.py` – `payment_method` JSON 컬럼 추가
- `alembic/versions/005_add_billing.py` – subscriptions, billing_histories 테이블 + workspaces.payment_method
- `app/main.py` – billing 라우터 등록

**Frontend**
- `hooks/useBilling.ts` – 7 훅 + 플랜 상수 (PLAN_PRICES, PLAN_ORDER, PLAN_FEATURES, PLAN_LABELS 등)
- `components/billing/PaymentMethodModal.tsx` – 결제 수단 등록/변경 모달
- `app/(dashboard)/billing/page.tsx` – 구독·결제 현황 (플랜 상태, 사용량 프로그레스바, 결제수단, 내역 테이블)
- `app/(dashboard)/billing/upgrade/page.tsx` – 플랜 변경 (4개 플랜 카드, 월간/연간 20% 할인 토글, 다운그레이드 경고)
- `components/layout/Sidebar.tsx` – /billing "구독·결제" 메뉴 (CreditCard 아이콘, Sprint 8 이전 이미 존재)

---

## DB 테이블 13개

| 테이블명 | 모델 | 주요 컬럼 |
|---|---|---|
| users | User | email(unique), hashed_password, name, role, is_active |
| workspaces | Workspace | owner_id(FK), name, plan(enum), is_active |
| workspace_members | WorkspaceMember | workspace_id(FK), user_id(FK), role(enum) |
| places | Place | workspace_id(FK), naver_place_id, name, alias, category, is_active |
| place_keywords | PlaceKeyword | place_id(FK), keyword, is_primary, is_active, group_name |
| keyword_rankings | KeywordRanking | keyword_id(FK), rank, case_type(enum), crawled_at |
| crawl_jobs | CrawlJob | keyword_id(FK), status(enum), scheduled/started/finished_at, result(JSONB), retry_count |
| media_companies | MediaCompany | name, contact_email, contact_phone, bank_account, is_active |
| orders | Order | workspace_id(FK), place_id(FK), product_id(FK), keyword_ids(JSONB), status, quantity, unit_price, total_amount, proof_url |
| product_types | ProductType | name, description, is_active, sort_order |
| products | Product | product_type_id(FK), name, base_price, unit, min_quantity, max_quantity, is_active, extra_data(JSONB) |
| notifications | Notification | user_id(FK), workspace_id(FK), type(enum), title, message, data(JSON), is_read, read_at |
| notification_settings | NotificationSetting | user_id(FK), notification_type(enum), in_app_enabled, email_enabled, kakao_enabled, sms_enabled |
| subscriptions | Subscription | workspace_id(FK), plan(enum), billing_cycle(monthly/yearly), status(active/cancelled/past_due/expired), amount, started_at, next_billing_at, cancelled_at |
| billing_histories | BillingHistory | workspace_id(FK), subscription_id(FK nullable), type(subscription/upgrade/downgrade/refund), plan, billing_cycle, amount, status(paid/failed/refunded), pg_transaction_id, description |

---

## NotificationType 25종

```python
# 주문 관련 (8)
ORDER_CREATED, ORDER_CONFIRMED, ORDER_ASSIGNED, ORDER_IN_PROGRESS,
ORDER_COMPLETED, ORDER_CANCELLED, ORDER_REFUND_REQUESTED, ORDER_REFUND_DECIDED

# 랭킹 관련 (5)
RANK_IMPROVED, RANK_DROPPED, RANK_TOP10, RANK_TOP3, RANK_FLUCTUATION

# 시스템 관련 (5)
PLAN_UPGRADED, PLAN_DOWNGRADED, PLAN_EXPIRED, CRAWL_COMPLETED, CRAWL_FAILED

# 워크스페이스 관련 (4)
MEMBER_INVITED, MEMBER_JOINED, MEMBER_LEFT, MEMBER_ROLE_CHANGED

# 결제 관련 (3)
PAYMENT_COMPLETED, PAYMENT_FAILED, PAYMENT_REFUNDED
```

---

## Redis 키 구조

| 키 패턴 | TTL | 용도 |
|---|---|---|
| `login_fail:{email}` | 900s (15분) | 로그인 실패 카운트 |
| `refresh:{user_id}` | 30일 | Refresh Token 저장 |
| `pwd_reset:{token}` | 3600s (1시간) | 비밀번호 재설정 토큰 |
| `email_verify:{token}` | 86400s (24시간) | 이메일 인증 토큰 |
| `crawl_count:{workspace_id}:{YYYY-MM-DD}` | KST 자정까지 | 일일 수동 크롤링 횟수 |

---

## 플랜 한도 (PLAN_LIMITS)

| 플랜 | max_places | max_keywords | crawl_per_day |
|---|---|---|---|
| free | 1 | 5 | 1 |
| starter | 5 | 30 | 2 |
| pro | 20 | 100 | 4 |
| enterprise | 999 | 999 | 4 |

---

## API 엔드포인트 요약

### Auth (`/api/v1/auth`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | /register | 회원가입 |
| POST | /login | 로그인 |
| POST | /refresh | 토큰 갱신 |
| POST | /logout | 로그아웃 |
| POST | /forgot-password | 비밀번호 재설정 이메일 |
| POST | /reset-password | 비밀번호 재설정 |
| GET | /me | 현재 유저 정보 |

### Workspaces (`/api/v1/workspaces`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /me | 유저 워크스페이스 목록 |
| GET | /{workspace_id} | 워크스페이스 상세 + 플랜 한도 |

### Places (`/api/v1/places`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | / | 장소 목록 |
| POST | / | 장소 등록 |
| GET | /dashboard-summary | 대시보드 요약 |
| GET | /{place_id} | 장소 상세 |
| PUT | /{place_id} | 장소 수정 |
| DELETE | /{place_id} | 장소 소프트 삭제 |
| POST | /{place_id}/crawl-now | 즉시 크롤링 (Redis 한도 체크) |

### Keywords (`/api/v1`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /places/{place_id}/keywords | 키워드 목록 (순위 포함) |
| POST | /places/{place_id}/keywords | 키워드 등록 |
| PUT | /places/{place_id}/keywords/{keyword_id} | 키워드 수정 |
| DELETE | /places/{place_id}/keywords/{keyword_id} | 키워드 소프트 삭제 |
| GET | /places/{place_id}/keywords/{keyword_id}/rankings | 순위 이력 |
| GET | /places/{place_id}/rankings/summary | 장소 전체 순위 요약 |

### Products (`/api/v1/products`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | / | 활성 상품 목록 (유형별 그룹) |

### Orders (`/api/v1/orders`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | / | 주문 목록 (status 필터, 페이지네이션) |
| POST | / | 주문 생성 + Mock 결제 페이로드 |
| GET | /{order_id} | 주문 상세 |
| POST | /{order_id}/cancel | 주문 취소 (pending만) |
| POST | /{order_id}/refund-request | 환불 요청 |

### Payments (`/api/v1/payments`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | /{payment_id}/complete | Mock PG 결제 완료 |

### Admin (`/api/v1/admin`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /dashboard | KPI + 최근주문 |
| GET | /orders | 전체 주문 목록 |
| GET | /orders/{order_id} | 주문 상세 (admin_notes 포함) |
| PATCH | /orders/{order_id}/status | 상태 변경 |
| POST | /orders/{order_id}/assign | 미디어사 배정 |
| POST | /orders/{order_id}/complete | 완료 처리 |
| POST | /orders/{order_id}/refund | 환불 결정 |
| GET | /media-companies | 목록 (통계 포함) |
| POST | /media-companies | 등록 |
| GET | /media-companies/{id} | 상세 + 최근 주문 |
| PUT | /media-companies/{id} | 수정 |
| DELETE | /media-companies/{id} | 소프트 삭제 |

### Notifications (`/api/v1`) ← Sprint 7 신규
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /notifications | 알림 목록 (is_read 필터, page/limit) |
| GET | /notifications/unread-count | 미읽음 알림 수 |
| POST | /notifications/{id}/read | 단건 읽음 처리 |
| POST | /notifications/read-all | 전체 읽음 처리 |
| DELETE | /notifications/{id} | 단건 삭제 |
| GET | /notifications/settings | 알림 수신 설정 조회 |
| PUT | /notifications/settings | 알림 수신 설정 일괄 저장 |

### Account (`/api/v1/account`) ← Sprint 7 신규
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /account/me | 내 프로필 |
| PUT | /account/me | 프로필 수정 (이름/전화) |
| POST | /account/change-password | 비밀번호 변경 |
| DELETE | /account/me | 회원 탈퇴 (소프트) |
| GET | /account/activity | 최근 활동 요약 |

### Workspace Members (`/api/v1/workspaces`) ← Sprint 7 신규
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /workspaces/{id}/members | 멤버 목록 |
| POST | /workspaces/{id}/members/invite | 멤버 초대 |
| PATCH | /workspaces/{id}/members/{user_id} | 역할 변경 |
| DELETE | /workspaces/{id}/members/{user_id} | 멤버 제거 |
| POST | /workspaces/{id}/transfer-ownership | 소유권 이전 |

### Billing (`/api/v1/billing`) ← Sprint 8 신규
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /billing/subscription | 현재 구독 조회 (플랜 한도 + 사용량 포함) |
| GET | /billing/history | 결제 내역 목록 (page, limit) |
| POST | /billing/upgrade | 플랜 업그레이드 (Mock PG txn, 알림 발송) |
| POST | /billing/downgrade | 플랜 다운그레이드 (초과 장소/키워드 비활성화) |
| POST | /billing/cancel | 구독 취소 |
| GET | /billing/payment-method | 결제 수단 조회 |
| POST | /billing/payment-method | 결제 수단 등록/변경 |

---

## 환경변수 (`.env.example` 기준)

```env
# DB
DATABASE_URL=postgresql://nplace:nplace1234@localhost:5432/nplace

# Redis
REDIS_URL=redis://localhost:6379

# JWT
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# App
ENVIRONMENT=development
DEBUG=true

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Next.js
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 코드 컨벤션

### Python (Backend)
- 모든 파일 상단 `"""` docstring + 한국어 주석 필수
- 의존성 주입: `Depends(get_current_user)`, `Depends(get_db)`
- 에러: `raise HTTPException(status_code=..., detail="한국어 메시지")`
- Pydantic v2: `model_config = {"from_attributes": True}`, `@field_validator`
- 비동기 Redis: `async def` + `await redis.xxx()`
- 동기 DB: SQLAlchemy sync Session (`Session`, not `AsyncSession`)
- Celery 태스크에서 DB 세션: `SessionLocal()` 직접 생성 (FastAPI 의존성 불가)

### TypeScript (Frontend)
- `"use client"` 필수 (App Router 클라이언트 컴포넌트)
- 한국어 주석 필수
- TanStack Query: `useQuery`, `useMutation`, `queryClient.invalidateQueries()`
- 상태: `useAuthStore()` → `workspace.id` = workspaceId
- API 호출: `api.get/post/put/delete` (lib/api.ts의 axios 인스턴스)
- 스타일: inline style (다크 테마 색상) + Tailwind 유틸리티 혼용
- 다크 테마 카드: `background: "rgba(255,255,255,0.04)"`, `border: "1px solid rgba(255,255,255,0.08)"`
- 포인트 컬러: `#00d4ff` (cyan)
- 에러 컬러: `#f87171` (red), 경고: `#fcd34d` (yellow)

---

## 주요 패키지 버전

### Backend
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.0
alembic>=1.13.0
pydantic[email]>=2.6.0
pydantic-settings>=2.2.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
redis[hiredis]>=5.0.0
celery[redis]>=5.3.0
```

### Frontend
```
next: 14.2.5
react: ^18.3.1
@tanstack/react-query: ^5.51.23
zustand: ^4.5.4
react-hook-form: ^7.52.1
zod: ^3.23.8
axios: ^1.7.2
recharts: ^2.12.7
date-fns: ^3.6.0
lucide-react: ^0.414.0
sonner: ^1.5.0
jose: ^5.6.3
```

---

## Sprint 9 예정 작업

### 우선순위 높음
1. **정산 관리** – `app/(admin)/admin/settlements/page.tsx`
   - 매체사별 정산 현황, 미정산 주문 목록, 정산 처리 (지급 완료 처리)
   - Backend: `GET /admin/settlements`, `POST /admin/settlements/{order_id}/pay`
2. **유저 관리** – `app/(admin)/admin/users/page.tsx`
   - 유저 목록 (검색/필터), 정지/활성화, 역할 변경
   - Backend: `GET /admin/users`, `PATCH /admin/users/{id}` (suspend/activate/role)
3. **실 결제 연동** – 토스페이먼츠 웹훅 처리
   - `POST /api/v1/payments/webhook/toss`

### 우선순위 중간
4. **통계·KPI 페이지** – `app/(admin)/admin/stats/dashboard/page.tsx`
   - 매출 트렌드 (Recharts), 주문 현황 도넛 차트, 워크스페이스 플랜 분포
5. **인사이트 페이지** – `app/(dashboard)/insights/page.tsx`
   - 워크스페이스 전체 키워드 순위 현황, 상위/하위 TOP 5, 순위 변동 추이

### 우선순위 낮음
6. **워크스페이스 관리 (어드민)** – `app/(admin)/admin/workspaces/page.tsx`
7. **CS 관리** – `app/(admin)/admin/support/page.tsx`
8. **WebSocket 알림** – polling 방식(30초) → SSE 또는 WebSocket으로 전환

---

## 실행 명령

```bash
# 환경변수 설정
cp .env.example .env

# 전체 서비스 시작 (backend + frontend + celery_worker + celery_beat 포함)
docker-compose up -d

# DB 마이그레이션 실행
docker-compose exec backend alembic upgrade head

# 로그 확인
docker-compose logs -f backend
docker-compose logs -f celery_worker

# 접속
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/api/v1
# API Docs: http://localhost:8000/docs
```

---

## Sprint 9 시작 시 새 채팅에서 사용법

이 파일 전체를 복사해서 새 채팅 첫 메시지로 붙여넣고 다음과 같이 요청하세요:

```
위 CONTEXT.md를 기반으로 Sprint 9을 시작합니다.
Sprint 1~8 파일 구조와 컨벤션 그대로 유지.
코드 생략 없이 실제 동작하는 완성 코드와 한국어 주석으로 작성.

[원하는 Sprint 9 작업 목록]
```

---

## 네이버 플레이스 파서 (naver_place_parser.py v5.0)

### 위치
- 파서: `/home/user/nplace-parser/parser/naver_place_parser.py`
- API 서버: `/home/user/nplace-project/parser_api.py` (포트 8000)
- PM2: `nplace-parser-api`

### 파서 v5.0 핵심 구조 (2026-03-20)

#### 수집 방식
| 항목 | 방식 | 건수 |
|------|------|------|
| 블로그 리뷰 | GraphQL `fsasReviews(input)` page=0,1,2... 병렬 호출 | 최대 100건 |
| 영수증 리뷰 | Apollo SSR + GraphQL `visitorReviews(size=10/20)` | 30-50건 |
| 사진 | sasImages + ugcModeling(origin 필드) + cpImages 멀티소스 | 최대 200장 |
| 영업시간 | Apollo newBusinessHours | 7일 전체 |
| 편의시설 | PlaceDetailBase.conveniences + InformationFacilities | 전체 |
| 메뉴 | Menu 타입 + PlaceDetail_BaeminMenu fallback | 전체 |

#### Apollo State 파싱 핵심
- `ROOT_QUERY → placeDetail({...}) → 서브키` 구조
- `ugcModeling` 사진: `url` 필드 None → `origin` 필드 사용
- `sasImages/ugcModeling/cpImages` 모두 독립 `if` 블록으로 처리 (elif 아님)

#### GraphQL 엔드포인트
- `https://api.place.naver.com/graphql`
- 블로그: `query fsasReviews($input: FsasReviewsInput)` + `page` 파라미터
- 영수증: `query visitorReviews($input: VisitorReviewsInput)` + `size=10/20`

#### 업종별 사진 소스
| 업종 | 사진 소스 |
|------|----------|
| restaurant/accommodation | sasImages (최대 30장/페이지, 전체 수천 장 중 30장만) |
| hairshop/nailshop | ugcModeling (origin 필드, 전체 수집) |
| hospital | ugcModeling (origin 필드) |
| place | ugcModeling + cpImages |
| 공통 | images(source:brand) 브랜드 이미지 |

#### 알려진 한계
- 영수증 리뷰: cursor 기반 페이지네이션 미지원 → 최대 30-50건
- 사진: URL/GraphQL 모두 start 파라미터 무시 → 항상 첫 30장만 (sasImages 제한)
- 파싱 소요시간: 업종별 2.5~4.5초

### API 엔드포인트
- `GET /` – 헬스체크
- `POST /api/parse` – URL/ID 파싱 (max_visitor_reviews, max_blog_reviews, max_photos 지원)
- `GET /api/parse/{place_id}?category=restaurant` – ID 직접 파싱
- `POST /api/parse/preview` – 빠른 미리보기 (홈탭만)
