from __future__ import annotations

from typing import Any

from epayroll.auth.passwords import verify_password
from epayroll.db.connection import get_connection

_ORG_ORDER = """
ORDER BY
    CASE
        WHEN o.id = '00000000-0000-0000-0000-000000000010'::uuid THEN 0
        WHEN o.razon_social ILIKE 'Easy Technology%%' THEN 1
        ELSE 2
    END,
    o.razon_social
"""


class UserRepository:
    def authenticate(self, email: str, password: str, database_url: str | None = None) -> dict[str, Any] | None:
        user = self.get_by_email(email, database_url=database_url)
        if not user or not user.get("activo"):
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user

    def get_by_email(self, email: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id, u.tenant_id, u.email, u.password_hash, u.nombres, u.activo,
                           t.nombre AS tenant_nombre
                    FROM app_users u
                    JOIN tenants t ON t.id = u.tenant_id AND t.activo = true
                    WHERE u.email = %s AND u.activo = true
                    """,
                    (email.strip().lower(),),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "email": str(row[2]),
            "password_hash": row[3],
            "nombres": row[4],
            "activo": row[5],
            "tenant_nombre": row[6],
        }

    def get_by_id(self, user_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id, u.tenant_id, u.email, u.nombres, u.activo, t.nombre
                    FROM app_users u
                    JOIN tenants t ON t.id = u.tenant_id
                    WHERE u.id = %s::uuid AND u.activo = true
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "email": str(row[2]),
            "nombres": row[3],
            "activo": row[4],
            "tenant_nombre": row[5],
        }

    def list_organizations_for_user(
        self, user_id: str, database_url: str | None = None
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT o.id, o.tenant_id, o.razon_social, o.ruc, o.activo,
                           os.periodo_pago::text, m.roles
                    FROM user_organization_memberships m
                    JOIN organizations o ON o.id = m.organization_id AND o.activo = true
                    LEFT JOIN organization_settings os ON os.organization_id = o.id
                    WHERE m.user_id = %s::uuid AND m.activo = true
                    {_ORG_ORDER}
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "tenant_id": str(r[1]),
                "razon_social": r[2],
                "ruc": r[3],
                "activo": r[4],
                "periodo_pago": r[5] or "QUINCENAL",
                "roles": list(r[6] or []),
            }
            for r in rows
        ]

    def user_has_org_access(
        self, user_id: str, organization_id: str, database_url: str | None = None
    ) -> bool:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM user_organization_memberships m
                    JOIN organizations o ON o.id = m.organization_id AND o.activo = true
                    WHERE m.user_id = %s::uuid
                      AND m.organization_id = %s::uuid
                      AND m.activo = true
                    """,
                    (user_id, organization_id),
                )
                return cur.fetchone() is not None

    def roles_for_user_org(
        self, user_id: str, organization_id: str, database_url: str | None = None
    ) -> tuple[str, ...]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT m.roles
                    FROM user_organization_memberships m
                    WHERE m.user_id = %s::uuid
                      AND m.organization_id = %s::uuid
                      AND m.activo = true
                    """,
                    (user_id, organization_id),
                )
                row = cur.fetchone()
        if not row or not row[0]:
            return ()
        return tuple(str(r) for r in row[0])
