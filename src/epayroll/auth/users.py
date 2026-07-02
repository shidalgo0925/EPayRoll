from __future__ import annotations

# Cuenta principal — siempre superusuario, no se puede dar de baja ni eliminar.
PROTECTED_SUPERUSER_EMAILS: frozenset[str] = frozenset(
    {"shidalgo@eastech.services", "shidalgo@easytech.services"}
)

# Roles asignables por empresa (membresía).
ASSIGNABLE_ROLES: tuple[str, ...] = (
    "tenant_admin",
    "payroll_admin",
    "rrhh",
    "contador",
    "gerente",
)

ROLE_LABELS: dict[str, str] = {
    "tenant_admin": "Administrador tenant",
    "payroll_admin": "Admin planilla",
    "rrhh": "Recursos humanos",
    "contador": "Contador",
    "gerente": "Gerente",
}


def is_protected_superuser(email: str) -> bool:
    return email.strip().lower() in PROTECTED_SUPERUSER_EMAILS


def can_manage_users(ctx) -> bool:
    return bool(getattr(ctx, "is_superuser", False)) or ctx.has_any_role(frozenset({"tenant_admin"}))


def can_modify_user(ctx, target: dict) -> bool:
    if getattr(ctx, "is_superuser", False):
        return True
    if target.get("is_superuser") or is_protected_superuser(str(target.get("email", ""))):
        return False
    return ctx.has_any_role(frozenset({"tenant_admin"}))
