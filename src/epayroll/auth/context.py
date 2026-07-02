from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthContext:
    """Contexto EN1: tenant + organización opcional + usuario."""

    tenant_id: str
    user_id: str | None = None
    organization_id: str | None = None
    roles: tuple[str, ...] = field(default_factory=tuple)
    authenticated: bool = True
    is_superuser: bool = False

    @classmethod
    def anonymous(cls) -> AuthContext:
        return cls(tenant_id="", authenticated=False)

    def has_role(self, role: str) -> bool:
        if self.is_superuser:
            return True
        return role in self.roles or "admin" in self.roles

    def has_any_role(self, roles: tuple[str, ...] | frozenset[str]) -> bool:
        if self.is_superuser:
            return True
        if "admin" in self.roles:
            return True
        allowed = set(roles)
        return bool(set(self.roles) & allowed)
