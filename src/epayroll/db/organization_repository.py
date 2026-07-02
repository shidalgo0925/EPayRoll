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

    @staticmethod
    def _map_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "razon_social": row[2],
            "ruc": row[3],
            "activo": row[4],
            "periodo_pago": row[5] or "QUINCENAL",
            "moneda": row[6] or "PAB",
            "zona_horaria": row[7] or "America/Panama",
        }

    _SELECT_ORG = """
        SELECT o.id, o.tenant_id, o.razon_social, o.ruc, o.activo,
               os.periodo_pago::text, os.moneda, os.zona_horaria
        FROM organizations o
        LEFT JOIN organization_settings os ON os.organization_id = o.id
    """

    def list_by_tenant(self, tenant_id: str, database_url: str | None = None) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    {OrganizationRepository._SELECT_ORG}
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
        return [self._map_row(r) for r in rows]

    def get(self, organization_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    {OrganizationRepository._SELECT_ORG}
                    WHERE o.id = %s::uuid AND o.activo = true
                    """,
                    (organization_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._map_row(row)

    def create(
        self,
        tenant_id: str,
        razon_social: str,
        ruc: str | None = None,
        periodo_pago: str = "QUINCENAL",
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
                    VALUES (%s::uuid, %s::payment_frequency)
                    ON CONFLICT (organization_id) DO NOTHING
                    """,
                    (org_id, periodo_pago),
                )
                conn.commit()
        return self.get(org_id, database_url=database_url) or {
            "id": org_id,
            "tenant_id": str(row[1]),
            "razon_social": row[2],
            "ruc": row[3],
            "activo": row[4],
            "periodo_pago": periodo_pago,
            "moneda": "PAB",
            "zona_horaria": "America/Panama",
        }

    def update(
        self,
        organization_id: str,
        *,
        razon_social: str | None = None,
        ruc: str | None = None,
        periodo_pago: str | None = None,
        moneda: str | None = None,
        zona_horaria: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        org_updates: list[str] = []
        org_params: list[Any] = []
        if razon_social is not None:
            org_updates.append("razon_social = %s")
            org_params.append(razon_social)
        if ruc is not None:
            org_updates.append("ruc = %s")
            org_params.append(ruc or None)

        settings_updates: list[str] = []
        settings_params: list[Any] = []
        if periodo_pago is not None:
            settings_updates.append("periodo_pago = %s::payment_frequency")
            settings_params.append(periodo_pago)
        if moneda is not None:
            settings_updates.append("moneda = %s")
            settings_params.append(moneda.upper())
        if zona_horaria is not None:
            settings_updates.append("zona_horaria = %s")
            settings_params.append(zona_horaria)

        if not org_updates and not settings_updates:
            row = self.get(organization_id, database_url=database_url)
            if not row:
                raise ValueError("Organización no encontrada")
            return row

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                if org_updates:
                    cur.execute(
                        f"""
                        UPDATE organizations
                        SET {", ".join(org_updates)}, updated_at = now()
                        WHERE id = %s::uuid AND activo = true
                        RETURNING id
                        """,
                        (*org_params, organization_id),
                    )
                    if not cur.fetchone():
                        raise ValueError("Organización no encontrada")
                elif not self.get(organization_id, database_url=database_url):
                    raise ValueError("Organización no encontrada")

                if settings_updates:
                    cur.execute(
                        f"""
                        UPDATE organization_settings
                        SET {", ".join(settings_updates)}, updated_at = now()
                        WHERE organization_id = %s::uuid
                        """,
                        (*settings_params, organization_id),
                    )
                conn.commit()

        row = self.get(organization_id, database_url=database_url)
        if not row:
            raise ValueError("Organización no encontrada")
        return row

    def deactivate(self, organization_id: str, database_url: str | None = None) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE organizations
                    SET activo = false, updated_at = now()
                    WHERE id = %s::uuid AND activo = true
                    RETURNING id
                    """,
                    (organization_id,),
                )
                if not cur.fetchone():
                    raise ValueError("Organización no encontrada")
                cur.execute(
                    """
                    UPDATE user_organization_memberships
                    SET activo = false, updated_at = now()
                    WHERE organization_id = %s::uuid AND activo = true
                    """,
                    (organization_id,),
                )
                conn.commit()
