from __future__ import annotations

from typing import Any

from epayroll.db.connection import get_connection


class OrganizationRepository:
    def tenant_exists(self, tenant_id: str, database_url: str | None = None) -> bool:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM tenants
                    WHERE id = %s::uuid AND activo = true
                    """,
                    (tenant_id,),
                )
                return cur.fetchone() is not None

    def get_tenant(self, tenant_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, nombre, slug, activo
                    FROM tenants
                    WHERE id = %s::uuid AND activo = true
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "nombre": row[1],
            "slug": row[2],
            "activo": row[3],
        }

    def list_by_tenant(self, tenant_id: str, database_url: str | None = None) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT o.id, o.tenant_id, o.razon_social, o.ruc, o.activo,
                           os.periodo_pago::text
                    FROM organizations o
                    LEFT JOIN organization_settings os ON os.organization_id = o.id
                    WHERE o.tenant_id = %s::uuid AND o.activo = true
                    ORDER BY
                        CASE
                            WHEN o.id = '00000000-0000-0000-0000-000000000010'::uuid THEN 0
                            WHEN o.razon_social ILIKE 'Easy Technology%%' THEN 1
                            ELSE 2
                        END,
                        o.razon_social
                    """,
                    (tenant_id,),
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
            }
            for r in rows
        ]

    def get(self, organization_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT o.id, o.tenant_id, o.razon_social, o.ruc, o.activo,
                           os.periodo_pago::text
                    FROM organizations o
                    LEFT JOIN organization_settings os ON os.organization_id = o.id
                    WHERE o.id = %s::uuid AND o.activo = true
                    """,
                    (organization_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "razon_social": row[2],
            "ruc": row[3],
            "activo": row[4],
            "periodo_pago": row[5] or "QUINCENAL",
        }

    def create(
        self,
        tenant_id: str,
        razon_social: str,
        ruc: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO organizations (tenant_id, razon_social, ruc)
                    VALUES (%s::uuid, %s, %s)
                    RETURNING id, tenant_id, razon_social, ruc, activo
                    """,
                    (tenant_id, razon_social, ruc),
                )
                row = cur.fetchone()
                org_id = str(row[0])
                cur.execute(
                    """
                    INSERT INTO organization_settings (organization_id, periodo_pago)
                    VALUES (%s::uuid, 'QUINCENAL'::payment_frequency)
                    ON CONFLICT (organization_id) DO NOTHING
                    """,
                    (org_id,),
                )
                conn.commit()
        return {
            "id": org_id,
            "tenant_id": str(row[1]),
            "razon_social": row[2],
            "ruc": row[3],
            "activo": row[4],
            "periodo_pago": "QUINCENAL",
        }
