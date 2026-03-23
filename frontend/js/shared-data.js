/**
 * shared-data.js — 전체 페이지 공유 목데이터
 * dashboard.html / places.html / place-status.html / orders.html 에서 공통 사용
 *
 * ── 카테고리 기준 (Sprint 12 통일) ──────────────────────────────
 *   blog           : 블로그 리뷰
 *   reward_traffic : 리워드 유입 (트래픽)
 *   reward_save    : 리워드 저장하기
 *   receipt        : 영수증 리뷰
 *   sns            : SNS (인스타그램 등)
 *
 * ── 상태 기준 (DB OrderStatus enum) ────────────────────────────
 *   pending     : 결제 대기
 *   confirmed   : 확인 완료
 *   in_progress : 진행 중
 *   completed   : 완료
 *   cancelled   : 취소
 *   refunded    : 환불 완료
 *   disputed    : 분쟁 처리
 *
 * ── 플레이스 ID 기준 ────────────────────────────────────────────
 *   내부 id   : 'p1' | 'p2' | 'p3'  (모든 파일 통일)
 *   naverMid  : 네이버 MID (실제 API 연동 시 이 값으로 /places/{id}/orders 호출)
 */

/* ═══════════════════════════════════════════════════════════════
   카테고리 메타 (아이콘, 레이블, 색상)
═══════════════════════════════════════════════════════════════ */
const CATEGORY_META = {
  blog:           { icon: '📝', label: '블로그',    color: '#3b82f6', bg: 'rgba(59,130,246,.15)' },
  reward_traffic: { icon: '🎯', label: '리워드유입', color: '#22c55e', bg: 'rgba(34,197,94,.15)'  },
  reward_save:    { icon: '🔖', label: '저장하기',   color: '#f59e0b', bg: 'rgba(245,158,11,.15)' },
  receipt:        { icon: '🧾', label: '영수증',     color: '#8b5cf6', bg: 'rgba(139,92,246,.15)' },
  sns:            { icon: '📸', label: 'SNS',        color: '#ec4899', bg: 'rgba(236,72,153,.15)'  },
};

/* ═══════════════════════════════════════════════════════════════
   주문 상태 메타 (DB 기준)
═══════════════════════════════════════════════════════════════ */
const STATUS_META = {
  pending:     { label: '결제 대기', color: '#f59e0b', bg: 'rgba(245,158,11,.15)',   cls: 'badge-yellow'  },
  confirmed:   { label: '확인 완료', color: '#3b82f6', bg: 'rgba(59,130,246,.15)',   cls: 'badge-blue'    },
  in_progress: { label: '진행 중',   color: '#22c55e', bg: 'rgba(34,197,94,.15)',    cls: 'badge-green'   },
  completed:   { label: '완료',      color: '#64748b', bg: 'rgba(100,116,139,.15)',  cls: 'badge-gray'    },
  cancelled:   { label: '취소',      color: '#ef4444', bg: 'rgba(239,68,68,.15)',    cls: 'badge-red'     },
  refunded:    { label: '환불 완료', color: '#ef4444', bg: 'rgba(239,68,68,.12)',    cls: 'badge-red'     },
  disputed:    { label: '분쟁 처리', color: '#8b5cf6', bg: 'rgba(139,92,246,.15)',   cls: 'badge-purple'  },
};

/* ═══════════════════════════════════════════════════════════════
   공유 주문 목데이터
   - id      : 주문 고유 ID
   - placeId : 'p1'|'p2'|'p3' (SHARED_PLACES의 id와 일치)
   - category: blog|reward_traffic|reward_save|receipt|sns
   - status  : pending|confirmed|in_progress|completed|cancelled|refunded|disputed
   - dailyQty: 일 수량 (없으면 null)
   - startDate/endDate: 'YYYY-MM-DD'
   - keywords: 작업 키워드 목록
═══════════════════════════════════════════════════════════════ */
const SHARED_ORDERS = [
  /* ── 업체 A (강남) ── */
  {
    id: 'ORD-1024',
    placeId: 'p1',
    product: '리워드 유입 — 프리미엄',
    category: 'reward_traffic',
    status: 'in_progress',
    dailyQty: 200,
    startDate: '2026-03-10', endDate: '2026-04-05',
    quantity: 5200, unitPrice: 150, totalAmount: 780000,
    keywords: ['강남 맛집', '테헤란로 맛집', '강남역 한식'],
  },
  {
    id: 'ORD-1018',
    placeId: 'p1',
    product: '저장하기 — 스탠다드',
    category: 'reward_save',
    status: 'in_progress',
    dailyQty: 100,
    startDate: '2026-03-15', endDate: '2026-04-05',
    quantity: 2200, unitPrice: 90, totalAmount: 198000,
    keywords: [],
  },
  {
    id: 'ORD-0991',
    placeId: 'p1',
    product: '리워드 유입 — 스탠다드',
    category: 'reward_traffic',
    status: 'completed',
    dailyQty: 150,
    startDate: '2026-03-01', endDate: '2026-03-16',
    quantity: 2400, unitPrice: 90, totalAmount: 216000,
    keywords: ['강남 점심', '역삼동 맛집'],
  },
  {
    id: 'ORD-0985',
    placeId: 'p1',
    product: '블로그 리뷰 — 스탠다드',
    category: 'blog',
    status: 'in_progress',
    dailyQty: null,
    startDate: '2026-03-20', endDate: '2026-04-03',
    quantity: 5, unitPrice: 15000, totalAmount: 75000,
    keywords: ['강남 맛집', '한식 맛집'],
  },

  /* ── 업체 B (홍대) ── */
  {
    id: 'ORD-1025',
    placeId: 'p2',
    product: '리워드 유입 — 스탠다드',
    category: 'reward_traffic',
    status: 'in_progress',
    dailyQty: 100,
    startDate: '2026-03-12', endDate: '2026-04-08',
    quantity: 2800, unitPrice: 90, totalAmount: 252000,
    keywords: ['홍대 맛집', '홍대입구역 맛집'],
  },
  {
    id: 'ORD-0998',
    placeId: 'p2',
    product: '블로그 리뷰 — 스탠다드',
    category: 'blog',
    status: 'pending',
    dailyQty: null,
    startDate: '2026-03-25', endDate: '2026-04-10',
    quantity: 3, unitPrice: 15000, totalAmount: 45000,
    keywords: [],
  },
  {
    id: 'ORD-0975',
    placeId: 'p2',
    product: '영수증 리뷰 — 스탠다드',
    category: 'receipt',
    status: 'completed',
    dailyQty: 2,
    startDate: '2026-03-05', endDate: '2026-03-19',
    quantity: 10, unitPrice: 5000, totalAmount: 50000,
    keywords: [],
  },

  /* ── 업체 C (청담) ── */
  {
    id: 'ORD-1030',
    placeId: 'p3',
    product: '블로그 리뷰 — 프리미엄',
    category: 'blog',
    status: 'in_progress',
    dailyQty: null,
    startDate: '2026-03-18', endDate: '2026-04-12',
    quantity: 4, unitPrice: 35000, totalAmount: 140000,
    keywords: [],
  },
  {
    id: 'ORD-1029',
    placeId: 'p3',
    product: '리워드 유입 — 스탠다드',
    category: 'reward_traffic',
    status: 'in_progress',
    dailyQty: 80,
    startDate: '2026-03-20', endDate: '2026-04-08',
    quantity: 1600, unitPrice: 90, totalAmount: 144000,
    keywords: ['청담 헤어샵', '청담동 미용실'],
  },
  {
    id: 'ORD-1010',
    placeId: 'p3',
    product: '저장하기 — 스탠다드',
    category: 'reward_save',
    status: 'completed',
    dailyQty: 50,
    startDate: '2026-03-01', endDate: '2026-03-20',
    quantity: 1000, unitPrice: 90, totalAmount: 90000,
    keywords: [],
  },
  {
    id: 'ORD-1005',
    placeId: 'p3',
    product: 'SNS 바이럴 — 인스타그램',
    category: 'sns',
    status: 'confirmed',
    dailyQty: null,
    startDate: '2026-03-28', endDate: '2026-04-10',
    quantity: 2, unitPrice: 25000, totalAmount: 50000,
    keywords: ['청담 헤어', '청담 미용'],
  },
];

/* 플레이스 ID로 주문 필터링 헬퍼 */
function getOrdersByPlace(placeId) {
  return SHARED_ORDERS.filter(o => o.placeId === placeId);
}

/* ═══════════════════════════════════════════════════════════════
   공유 플레이스 기본 정보 (모든 페이지 공통)
═══════════════════════════════════════════════════════════════ */
const SHARED_PLACES = [
  {
    id: 'p1',
    naverMid: '1005166855',
    name: '업체 A (강남)',
    category: '한식·백반',
    address: '서울특별시 강남구 테헤란로 123 1층',
    naverUrl: 'https://map.naver.com/v5/entry/place/1005166855',
    crawlStatus: 'ok',
    crawledAt: '2026-03-19 06:00',
    reviewCount: 342, reviewCountPrev: 315,
    avgRating: 4.6,
    blogReviewCount: 128, blogReviewPrev: 115,
    visitorMonthly: 4200, visitorPrev: 3900,
    rankKw: '강남 맛집', rankPos: 3, rankPrev: 5,
  },
  {
    id: 'p2',
    naverMid: '19797085',
    name: '업체 B (홍대)',
    category: '한식·분식',
    address: '서울특별시 마포구 홍대입구로 78 2층',
    naverUrl: 'https://map.naver.com/v5/entry/place/19797085',
    crawlStatus: 'warn',
    crawledAt: '2026-03-19 06:00',
    reviewCount: 187, reviewCountPrev: 172,
    avgRating: 4.3,
    blogReviewCount: 64, blogReviewPrev: 58,
    visitorMonthly: 2100, visitorPrev: 1980,
    rankKw: '홍대 맛집', rankPos: 2, rankPrev: 3,
  },
  {
    id: 'p3',
    naverMid: '12345678',
    name: '업체 C (청담)',
    category: '헤어·뷰티',
    address: '서울 강남구 청담동 118-3',
    naverUrl: 'https://map.naver.com/v5/entry/place/12345678',
    crawlStatus: 'ok',
    crawledAt: '2026-03-23 06:00',
    reviewCount: 95, reviewCountPrev: 88,
    avgRating: 4.8,
    blogReviewCount: 42, blogReviewPrev: 35,
    visitorMonthly: 1450, visitorPrev: 1320,
    rankKw: '청담 헤어샵', rankPos: 4, rankPrev: 7,
  },
];
