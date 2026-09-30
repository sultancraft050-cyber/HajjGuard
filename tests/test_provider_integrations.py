from unittest.mock import patch

from django.test import SimpleTestCase

from services.integrations import PROVIDERS, ProviderAdapter, SandboxAdapter
from services.haramain_adapter import HaramainLiveAdapter


class ProviderIntegrationContractTests(SimpleTestCase):
    def test_all_connectors_are_provider_neutral_and_sandboxed_by_default(self):
        self.assertEqual(set(PROVIDERS), {
            'nafath', 'nusuk_ministry', 'scada_cctv', 'emergency_gateway', 'wallet'
        })
        for key, adapter in PROVIDERS.items():
            self.assertEqual(adapter.health_check().status, 'sandbox', key)
            self.assertIsInstance(adapter.capabilities(), list)

    def test_base_adapter_is_disabled_until_authorized(self):
        result = ProviderAdapter().health_check()
        self.assertEqual(result.status, 'disabled')
        self.assertFalse(result.data['enabled'])

    def test_haramain_adapter_requires_explicit_authorization_gate(self):
        with patch.dict('os.environ', {
            'HAJJGUARD_ENABLE_HARAMAIN_PROVIDER': '1',
            'HAJJGUARD_HARAMAIN_AUTHORIZED': '0',
        }, clear=False):
            result = HaramainLiveAdapter.fetch_live_status()
        self.assertFalse(result['success'])
        self.assertEqual(result['source'], 'SIMULATION_HARAMAIN_TELEMETRY')

