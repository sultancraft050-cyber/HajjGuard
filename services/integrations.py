"""Provider-neutral integration contracts and explicit sandbox implementations.

No class in this module contacts a government or emergency provider. Live adapters
must be added only after written authorization, provider specifications, and secrets
are supplied through the deployment environment.
"""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IntegrationResult:
    status: str
    data: dict[str, Any]
    external_reference: str = ''
    error_category: str = ''


class ProviderAdapter:
    provider_key = 'base'

    def health_check(self) -> IntegrationResult:
        return IntegrationResult('disabled', {'enabled': False}, error_category='NOT_AUTHORIZED')

    def capabilities(self) -> list[str]:
        return []

    def create_or_refresh_authorization(self, **kwargs: Any) -> IntegrationResult:
        return IntegrationResult('disabled', {}, error_category='NOT_AUTHORIZED')

    def submit_or_fetch(self, **kwargs: Any) -> IntegrationResult:
        return IntegrationResult('disabled', {}, error_category='NOT_AUTHORIZED')

    def normalize_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def revoke_or_disconnect(self, **kwargs: Any) -> IntegrationResult:
        return IntegrationResult('disabled', {}, error_category='NOT_AUTHORIZED')


class SandboxAdapter(ProviderAdapter):
    """Deterministic provider contract for tests and academic demonstrations."""
    def __init__(self, provider_key: str, capabilities: list[str] | None = None):
        self.provider_key = provider_key
        self._capabilities = capabilities or []

    def health_check(self) -> IntegrationResult:
        return IntegrationResult('sandbox', {'provider': self.provider_key, 'enabled': True, 'synthetic': True})

    def capabilities(self) -> list[str]:
        return list(self._capabilities)

    def submit_or_fetch(self, **kwargs: Any) -> IntegrationResult:
        return IntegrationResult('sandbox', self.normalize_response(kwargs))


PROVIDERS = {
    'nafath': SandboxAdapter('nafath', ['identity.verify']),
    'nusuk_ministry': SandboxAdapter('nusuk_ministry', ['permit.read', 'group.read']),
    'scada_cctv': SandboxAdapter('scada_cctv', ['telemetry.ingest']),
    'emergency_gateway': SandboxAdapter('emergency_gateway', ['incident.submit']),
    'wallet': SandboxAdapter('wallet', ['safety_pass.create']),
}
