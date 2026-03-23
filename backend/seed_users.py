"""
DB 초기 테스트 데이터 seed 스크립트
실행: cd backend && python3 seed_users.py

생성 계정:
  admin@nplace.io   / password123   (일반 유저, PRO 플랜)
  superadmin@nplace.io / admin1234! (슈퍼어드민)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.workspace import Workspace, WorkspaceMember, WorkspacePlan, MemberRole

def seed():
    db: Session = SessionLocal()
    try:
        # ── 1. 유저 생성 ──────────────────────────────────────
        users_to_create = [
            {
                "email": "admin@nplace.io",
                "password": "password123",
                "name": "김대표",
                "role": UserRole.USER,
                "is_active": True,
                "email_verified": True,
            },
            {
                "email": "superadmin@nplace.io",
                "password": "admin1234!",
                "name": "이관리자",
                "role": UserRole.SUPERADMIN,
                "is_active": True,
                "email_verified": True,
            },
        ]

        created_users = {}
        for u_data in users_to_create:
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            if existing:
                print(f"  ✅ 이미 존재: {u_data['email']}")
                created_users[u_data["email"]] = existing
                continue

            user = User(
                email=u_data["email"],
                hashed_password=hash_password(u_data["password"]),
                name=u_data["name"],
                role=u_data["role"],
                is_active=u_data["is_active"],
                email_verified=u_data["email_verified"],
            )
            db.add(user)
            db.flush()
            created_users[u_data["email"]] = user
            print(f"  ✨ 유저 생성: {u_data['email']}")

        db.commit()
        # flush 후 refresh
        for email, user in created_users.items():
            db.refresh(user)

        # ── 2. 워크스페이스 생성 ──────────────────────────────
        admin_user = created_users["admin@nplace.io"]
        superadmin_user = created_users["superadmin@nplace.io"]

        workspaces_to_create = [
            {
                "owner": admin_user,
                "name": "맛있는 식당 본점",
                "plan": WorkspacePlan.PRO,
            },
            {
                "owner": superadmin_user,
                "name": "nplace.io 운영팀",
                "plan": WorkspacePlan.ENTERPRISE,
            },
        ]

        for ws_data in workspaces_to_create:
            existing_ws = db.query(Workspace).filter(
                Workspace.owner_id == ws_data["owner"].id,
                Workspace.name == ws_data["name"],
            ).first()
            if existing_ws:
                print(f"  ✅ 워크스페이스 이미 존재: {ws_data['name']}")
                continue

            ws = Workspace(
                owner_id=ws_data["owner"].id,
                name=ws_data["name"],
                plan=ws_data["plan"],
                is_active=True,
            )
            db.add(ws)
            db.flush()

            # 오너를 멤버로도 추가
            member = WorkspaceMember(
                workspace_id=ws.id,
                user_id=ws_data["owner"].id,
                role=MemberRole.OWNER,
            )
            db.add(member)
            print(f"  ✨ 워크스페이스 생성: {ws_data['name']} ({ws_data['plan'].value})")

        db.commit()

        # ── 3. 결과 확인 ──────────────────────────────────────
        print("\n📋 DB 확인:")
        for user in db.query(User).all():
            ws = db.query(Workspace).filter(Workspace.owner_id == user.id).first()
            ws_name = ws.name if ws else "(없음)"
            print(f"  👤 {user.email} | {user.name} | {user.role.value} | ws: {ws_name}")

        print("\n✅ Seed 완료!")

    except Exception as e:
        db.rollback()
        print(f"❌ 오류: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
