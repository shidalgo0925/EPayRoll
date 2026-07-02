from __future__ import annotations

from typing import Any

from epayroll.auth.passwords import hash_password, verify_password

from epayroll.auth.users import is_protected_superuser
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

# Emails legacy que redirigen al usuario canónico (migración sin bloquear acceso).
_LEGACY_EMAIL_ALIASES: dict[str, str] = {
    "shidalgo@easytech.services": "shidalgo@eastech.services",
}


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    return _LEGACY_EMAIL_ALIASES.get(normalized, normalized)


def _map_user_row(row: tuple) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "email": str(row[2]),
        "nombres": row[3],
        "activo": row[4],
        "is_superuser": bool(row[5]),
        "password_hash": row[6] if len(row) > 6 else None,
        "tenant_nombre": row[7] if len(row) > 7 else None,
    }


class UserRepository:
    def authenticate(self, email: str, password: str, database_url: str | None = None) -> dict[str, Any] | None:
        user = self.get_by_email(_normalize_email(email), database_url=database_url)
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
                           u.is_superuser, t.nombre AS tenant_nombre
                    FROM app_users u
                    JOIN tenants t ON t.id = u.tenant_id AND t.activo = true
                    WHERE u.email = %s AND u.activo = true
                    """,
                    (_normalize_email(email),),
                )
                row = cur.fetchone()
        if not row:
            return None
        mapped = _map_user_row((row[0], row[1], row[2], row[4], row[5], row[6], row[3], row[7]))
        mapped["password_hash"] = row[3]
        return mapped

    def get_by_id(self, user_id: str, database_url: str | None = None, *, include_inactive: bool = False) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT u.id, u.tenant_id, u.email, u.nombres, u.activo, u.is_superuser, t.nombre
                    FROM app_users u
                    JOIN tenants t ON t.id = u.tenant_id
                    WHERE u.id = %s::uuid {'AND u.activo = true' if not include_inactive else ''}
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _map_user_row(row)

    def list_organizations_for_user(
        self, user_id: str, database_url: str | None = None
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT o.id, o.tenant_id, o.razon_social, o.ruc, o.activo,
                           os.periodo_pago::text, m.roles,
                           os.moneda, os.zona_horaria
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
                "moneda": r[7] or "PAB",
                "zona_horaria": r[8] or "America/Panama",
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

    def grant_organization_access(
        self,
        user_id: str,
        organization_id: str,
        roles: list[str] | tuple[str, ...],
        database_url: str | None = None,
    ) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_organization_memberships (user_id, organization_id, roles)
                    VALUES (%s::uuid, %s::uuid, %s::text[])
                    ON CONFLICT (user_id, organization_id) DO UPDATE SET
                        roles = EXCLUDED.roles,
                        activo = true,
                        updated_at = now()
                    """,
                    (user_id, organization_id, list(roles)),
                )
            conn.commit()

    def list_memberships(self, user_id: str, database_url: str | None = None) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT m.organization_id, o.razon_social, m.roles, m.activo
                    FROM user_organization_memberships m
                    JOIN organizations o ON o.id = m.organization_id
                    WHERE m.user_id = %s::uuid
                    ORDER BY o.razon_social
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "organization_id": str(r[0]),
                "razon_social": r[1],
                "roles": list(r[2] or []),
                "activo": r[3],
            }
            for r in rows
        ]

    def list_by_tenant(self, tenant_id: str, database_url: str | None = None) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id, u.tenant_id, u.email, u.nombres, u.activo, u.is_superuser, t.nombre
                    FROM app_users u
                    JOIN tenants t ON t.id = u.tenant_id
                    WHERE u.tenant_id = %s::uuid
                    ORDER BY u.is_superuser DESC, u.email
                    """,
                    (tenant_id,),
                )
                rows = cur.fetchall()
        users = [_map_user_row(r) for r in rows]
        for user in users:
            user["memberships"] = self.list_memberships(user["id"], database_url=database_url)
        return users

    def create(
        self,
        tenant_id: str,
        email: str,
        password: str,
        nombres: str | None,
        *,
        is_superuser: bool = False,
        memberships: list[dict[str, Any]] | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        email_norm = _normalize_email(email)
        pwd_hash = hash_password(password)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_users (tenant_id, email, password_hash, nombres, is_superuser)
                    VALUES (%s::uuid, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (tenant_id, email_norm, pwd_hash, nombres, is_superuser),
                )
                user_id = str(cur.fetchone()[0])
                for m in memberships or []:
                    cur.execute(
                        """
                        INSERT INTO user_organization_memberships (user_id, organization_id, roles)
                        VALUES (%s::uuid, %s::uuid, %s::text[])
                        ON CONFLICT (user_id, organization_id) DO UPDATE SET
                            roles = EXCLUDED.roles,
                            activo = true,
                            updated_at = now()
                        """,
                        (user_id, m["organization_id"], list(m.get("roles") or ["payroll_admin"])),
                    )
                conn.commit()
        row = self.get_by_id(user_id, database_url=database_url, include_inactive=True)
        if not row:
            raise ValueError("No se pudo crear usuario")
        row["memberships"] = self.list_memberships(user_id, database_url=database_url)
        return row

    def update(
        self,
        user_id: str,
        *,
        nombres: str | None = None,
        password: str | None = None,
        activo: bool | None = None,
        is_superuser: bool | None = None,
        memberships: list[dict[str, Any]] | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        updates: list[str] = []
        params: list[Any] = []
        if nombres is not None:
            updates.append("nombres = %s")
            params.append(nombres)
        if password:
            updates.append("password_hash = %s")
            params.append(hash_password(password))
        if activo is not None:
            updates.append("activo = %s")
            params.append(activo)
        if is_superuser is not None:
            updates.append("is_superuser = %s")
            params.append(is_superuser)

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                if updates:
                    cur.execute(
                        f"""
                        UPDATE app_users
                        SET {", ".join(updates)}, updated_at = now()
                        WHERE id = %s::uuid
                        RETURNING id
                        """,
                        (*params, user_id),
                    )
                    if not cur.fetchone():
                        raise ValueError("Usuario no encontrado")

                if memberships is not None:
                    cur.execute(
                        """
                        UPDATE user_organization_memberships
                        SET activo = false, updated_at = now()
                        WHERE user_id = %s::uuid
                        """,
                        (user_id,),
                    )
                    for m in memberships:
                        if not m.get("organization_id"):
                            continue
                        cur.execute(
                            """
                            INSERT INTO user_organization_memberships (user_id, organization_id, roles)
                            VALUES (%s::uuid, %s::uuid, %s::text[])
                            ON CONFLICT (user_id, organization_id) DO UPDATE SET
                                roles = EXCLUDED.roles,
                                activo = true,
                                updated_at = now()
                            """,
                            (user_id, m["organization_id"], list(m.get("roles") or ["payroll_admin"])),
                        )
                conn.commit()

        row = self.get_by_id(user_id, database_url=database_url, include_inactive=True)
        if not row:
            raise ValueError("Usuario no encontrado")
        row["memberships"] = self.list_memberships(user_id, database_url=database_url)
        return row

    def deactivate(self, user_id: str, database_url: str | None = None) -> None:
        user = self.get_by_id(user_id, database_url=database_url, include_inactive=True)
        if not user:
            raise ValueError("Usuario no encontrado")
        if user.get("is_superuser") or is_protected_superuser(str(user.get("email", ""))):
            raise ValueError("No se puede dar de baja al superusuario del sistema")
        self.update(user_id, activo=False, database_url=database_url)
