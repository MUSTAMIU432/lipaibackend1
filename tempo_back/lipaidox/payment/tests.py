"""
Payment gateway health — what the "Payments aren't live yet" message hinges on.
No database and no network: NBC's client is stubbed.

    ./test.sh quick
"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from lipaidox.payment.gateways import nbc_client
from lipaidox.payment.health import gateway_health

PROBE = "lipaidox.payment.health.nbc_client.get_payment"


@override_settings(PAYMENT_GATEWAY_DEFAULT="nbc", NBC_API_KEY="k")
class LiveGatewayTests(SimpleTestCase):
    def test_404_means_key_accepted_and_live(self):
        with mock.patch(PROBE, side_effect=nbc_client.NbcError("Order not found", 404)):
            h = gateway_health()
        self.assertTrue(h["live"])
        self.assertEqual((h["reachable"], h["authenticated"]), (True, True))
        self.assertEqual(h["problems"], [])

    def test_401_means_key_rejected(self):
        with mock.patch(PROBE, side_effect=nbc_client.NbcError("Unauthorized", 401)):
            h = gateway_health()
        self.assertFalse(h["live"])
        self.assertEqual((h["reachable"], h["authenticated"]), (True, False))
        self.assertIn("rejected the API key", h["problems"][0])

    def test_unreachable_portal(self):
        with mock.patch(PROBE, side_effect=nbc_client.NbcError("Could not reach the payment gateway", 502)):
            h = gateway_health()
        self.assertFalse(h["live"])
        self.assertIs(h["reachable"], False)

    @override_settings(NBC_API_KEY="super-secret-key-value")
    def test_health_never_contains_the_key(self):
        import json

        for exc in (nbc_client.NbcError("Order not found", 404), nbc_client.NbcError("Unauthorized", 401)):
            with mock.patch(PROBE, side_effect=exc):
                self.assertNotIn("super-secret-key-value", json.dumps(gateway_health()))

    def test_no_probe_trusts_configuration(self):
        with mock.patch(PROBE) as probe:
            h = gateway_health(probe=False)
        probe.assert_not_called()
        self.assertTrue(h["live"])
        self.assertIsNone(h["authenticated"])


class NotLiveTests(SimpleTestCase):
    @override_settings(PAYMENT_GATEWAY_DEFAULT="simulated", NBC_API_KEY="")
    def test_simulated_is_never_live(self):
        with mock.patch(PROBE) as probe:
            h = gateway_health()
        probe.assert_not_called()          # no call to NBC when it isn't even selected
        self.assertFalse(h["live"])
        self.assertEqual(h["gateway"], "simulated")
        self.assertEqual(len(h["problems"]), 2)

    @override_settings(PAYMENT_GATEWAY_DEFAULT="nbc", NBC_API_KEY="")
    def test_nbc_without_key_is_not_live(self):
        h = gateway_health()
        self.assertFalse(h["live"])
        self.assertEqual(h["gateway"], "nbc")
        self.assertFalse(h["keyConfigured"])
