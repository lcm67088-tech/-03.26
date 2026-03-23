-- ================================================================
-- seed_product_types.sql
-- ProductType + Product 초기 데이터 (Sprint 12 카테고리 통일 기준)
-- 카테고리: blog / reward_traffic / reward_save / receipt / sns
-- 실행: psql $DATABASE_URL -f seed_product_types.sql
-- ================================================================

-- ── ProductType 5종 ─────────────────────────────────────────────
INSERT INTO product_types (id, name, description, is_active, sort_order, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'blog',           '블로그 리뷰 작성 서비스',          true, 1, NOW(), NOW()),
  (gen_random_uuid(), 'reward_traffic', '리워드 유입 (트래픽) 서비스',       true, 2, NOW(), NOW()),
  (gen_random_uuid(), 'reward_save',    '리워드 저장하기 서비스',             true, 3, NOW(), NOW()),
  (gen_random_uuid(), 'receipt',        '영수증 리뷰 서비스',                true, 4, NOW(), NOW()),
  (gen_random_uuid(), 'sns',            'SNS (인스타그램 등) 바이럴 서비스', true, 5, NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

-- ── Product 샘플 (ProductType FK 참조) ──────────────────────────
-- 블로그 상품
INSERT INTO products (id, product_type_id, name, description, base_price, unit, min_quantity, max_quantity, is_active, sort_order, extra_data, created_at, updated_at)
SELECT
  gen_random_uuid(),
  pt.id,
  '블로그 리뷰 — 스탠다드',
  '전문 블로거가 작성하는 네이버 블로그 리뷰',
  15000, '개', 1, 50, true, 1,
  '{"badge": "인기", "features": ["7일 내 완료", "키워드 포함", "사진 5장 이상"]}'::jsonb,
  NOW(), NOW()
FROM product_types pt WHERE pt.name = 'blog'
ON CONFLICT DO NOTHING;

INSERT INTO products (id, product_type_id, name, description, base_price, unit, min_quantity, max_quantity, is_active, sort_order, extra_data, created_at, updated_at)
SELECT
  gen_random_uuid(),
  pt.id,
  '블로그 리뷰 — 프리미엄',
  '파워블로거가 작성하는 고품질 블로그 리뷰',
  35000, '개', 1, 20, true, 2,
  '{"badge": "프리미엄", "features": ["10일 내 완료", "2,000자 이상", "사진 10장 이상", "SEO 최적화"]}'::jsonb,
  NOW(), NOW()
FROM product_types pt WHERE pt.name = 'blog'
ON CONFLICT DO NOTHING;

-- 리워드 유입 상품
INSERT INTO products (id, product_type_id, name, description, base_price, unit, min_quantity, max_quantity, is_active, sort_order, extra_data, created_at, updated_at)
SELECT
  gen_random_uuid(),
  pt.id,
  '리워드 유입 — 스탠다드',
  '키워드 검색 후 플레이스 방문 유입',
  90, '타수', 100, 10000, true, 1,
  '{"badge": null, "features": ["일 100~500타 가능", "키워드별 분산 유입", "실시간 현황 확인"]}'::jsonb,
  NOW(), NOW()
FROM product_types pt WHERE pt.name = 'reward_traffic'
ON CONFLICT DO NOTHING;

INSERT INTO products (id, product_type_id, name, description, base_price, unit, min_quantity, max_quantity, is_active, sort_order, extra_data, created_at, updated_at)
SELECT
  gen_random_uuid(),
  pt.id,
  '리워드 유입 — 프리미엄',
  '프리미엄 매체사를 통한 고품질 유입',
  150, '타수', 100, 5000, true, 2,
  '{"badge": "프리미엄", "features": ["실계정 유입", "체류시간 보장", "봇 0%"]}'::jsonb,
  NOW(), NOW()
FROM product_types pt WHERE pt.name = 'reward_traffic'
ON CONFLICT DO NOTHING;

-- 리워드 저장하기 상품
INSERT INTO products (id, product_type_id, name, description, base_price, unit, min_quantity, max_quantity, is_active, sort_order, extra_data, created_at, updated_at)
SELECT
  gen_random_uuid(),
  pt.id,
  '저장하기 — 스탠다드',
  '네이버 플레이스 저장하기 수 증가',
  90, '회', 100, 5000, true, 1,
  '{"badge": null, "features": ["일 50~200회 가능", "실계정 저장", "저장 유지 보장"]}'::jsonb,
  NOW(), NOW()
FROM product_types pt WHERE pt.name = 'reward_save'
ON CONFLICT DO NOTHING;

-- 영수증 리뷰 상품
INSERT INTO products (id, product_type_id, name, description, base_price, unit, min_quantity, max_quantity, is_active, sort_order, extra_data, created_at, updated_at)
SELECT
  gen_random_uuid(),
  pt.id,
  '영수증 리뷰 — 스탠다드',
  '실제 방문 영수증 기반 네이버 리뷰',
  5000, '개', 5, 100, true, 1,
  '{"badge": null, "features": ["실방문 기반", "별점 4~5점", "키워드 자연 포함"]}'::jsonb,
  NOW(), NOW()
FROM product_types pt WHERE pt.name = 'receipt'
ON CONFLICT DO NOTHING;

-- SNS 상품
INSERT INTO products (id, product_type_id, name, description, base_price, unit, min_quantity, max_quantity, is_active, sort_order, extra_data, created_at, updated_at)
SELECT
  gen_random_uuid(),
  pt.id,
  'SNS 바이럴 — 인스타그램',
  '인스타그램 위치태그 + 해시태그 포스팅',
  25000, '개', 1, 30, true, 1,
  '{"badge": null, "features": ["팔로워 1,000+ 계정", "위치태그 필수", "해시태그 10개 이상"]}'::jsonb,
  NOW(), NOW()
FROM product_types pt WHERE pt.name = 'sns'
ON CONFLICT DO NOTHING;
