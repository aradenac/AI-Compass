from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_health_reports_a_healthy_database(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_unknown_api_path_is_not_demo_data(self):
        response = self.client.get("/api/v1/models")
        self.assertEqual(response.status_code, 404)
