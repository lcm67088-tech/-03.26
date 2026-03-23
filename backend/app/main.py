"""
nplace.io FastAPI 애플리케이션 진입점
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import SessionLocal
from app.routers import auth, workspaces, places, keywords, admin
from app.routers.orders import orders_router, products_router, payments_router
from app.routers.notifications import router as notifications_router  # Sprint 7
from app.routers.account import router as account_router              # Sprint 7
from app.routers.workspace_members import router as workspace_members_router  # Sprint 7
from app.routers.billing import router as billing_router                      # Sprint 8
from app.routers.admin_users import router as admin_users_router              # Sprint 9
from app.routers.admin_workspaces import router as admin_workspaces_router    # Sprint 9
from app.routers.admin_settlements import router as admin_settlements_router  # Sprint 9
from app.routers.admin_stats import router as admin_stats_router              # Sprint 9
from app.utils.seed import seed_products


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 이벤트 핸들러"""
    # 시작 시 기본 상품 시드 실행 (테이블이 비어있을 때만)
    try:
        db = SessionLocal()
        seed_products(db)
        db.close()
    except Exception as e:
        print(f"[seed] 시드 실행 중 오류 (DB 미준비 상태일 수 있음): {e}")
    print("✅ nplace.io API 서버 시작")
    yield
    print("🔴 nplace.io API 서버 종료")


# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="nplace.io API",
    description="네이버 플레이스 마케팅 최적화 SaaS 플랫폼 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# 라우터 등록
# =====================
app.include_router(auth.router, prefix="/api/v1/auth", tags=["인증"])
app.include_router(workspaces.router, prefix="/api/v1/workspaces", tags=["워크스페이스"])
app.include_router(places.router, prefix="/api/v1/places", tags=["장소"])
# keywords 라우터: /api/v1/places/{place_id}/keywords 형태이므로 /api/v1 prefix 사용
app.include_router(keywords.router, prefix="/api/v1", tags=["키워드"])
app.include_router(products_router, prefix="/api/v1/products", tags=["상품"])
app.include_router(orders_router, prefix="/api/v1/orders", tags=["주문"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["결제"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["어드민"])
# ── Sprint 7 신규 라우터 ──────────────────────────────────────
app.include_router(notifications_router, prefix="/api/v1", tags=["알림"])
app.include_router(account_router, prefix="/api/v1", tags=["계정"])
app.include_router(workspace_members_router, prefix="/api/v1", tags=["워크스페이스 멤버"])
# ── Sprint 8 신규 라우터 ──────────────────────────────────────
app.include_router(billing_router, prefix="/api/v1", tags=["빌링"])
# ── Sprint 9 신규 라우터 (어드민 심화) ────────────────────────
app.include_router(admin_users_router, prefix="/api/v1", tags=["어드민-유저관리"])
app.include_router(admin_workspaces_router, prefix="/api/v1", tags=["어드민-워크스페이스관리"])
app.include_router(admin_settlements_router, prefix="/api/v1", tags=["어드민-정산관리"])
app.include_router(admin_stats_router, prefix="/api/v1", tags=["어드민-통계"])


# =====================
# 기본 엔드포인트
# =====================
@app.get("/health", tags=["헬스체크"])
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok", "service": "nplace.io", "version": "1.0.0"}


@app.get("/", tags=["루트"])
async def root():
    """루트 엔드포인트"""
    return {
        "message": "nplace.io API",
        "docs": "/docs",
        "health": "/health",
    }
