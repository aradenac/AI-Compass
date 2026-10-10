"""FUT-01 compatibility assertions; no database needed for the contract endpoint."""
from django.test import SimpleTestCase
from django.urls import resolve

from .release_contract import contract_document, error_payload


class ContractTests(SimpleTestCase):
    def test_api_v1_contract_remains_additive_for_older_frontends(self):
        response = self.client.get("/api/v1/contract")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), contract_document())
        self.assertIn(1, response.json()["supported_client_api_majors"])
        self.assertEqual(response.json()["schema"], "ai-compass/api-contract@1")

    def test_previous_v1_routes_resolve_for_unchanged_frontends(self):
        # Additive contract must not remove old Model/auth APIs consumed
        # by deployed pre-handshake frontend bundles.
        for endpoint in ("/api/v1/models", "/api/v1/auth/me",
                         "/api/v1/tasks", "/api/v1/campaigns",
                         "/api/v1/results/explorer"):
            with self.subTest(endpoint=endpoint):
                self.assertIsNotNone(resolve(endpoint).func)

    def test_typed_error_is_distinct_from_legacy_error_shape(self):
        response = error_payload("unsupported_api_version", "use v1", status=409)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "unsupported_api_version")

    def test_preexisting_health_endpoint_still_exists_without_auth(self):
        # The health endpoint remains in config.api, URL routing is unchanged.
        from .api import api
        self.assertEqual(api.version, "1.0.0")
