"""Unit tests for weather CLI helpers."""
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers under test (imported directly so tests don't trigger the script body)
# ---------------------------------------------------------------------------

# get_aqi_category
from main import get_aqi_category  # noqa: E402 — requires main to be importable


class TestGetAqiCategory(unittest.TestCase):
    def test_good(self):
        self.assertEqual(get_aqi_category(0), "Good")
        self.assertEqual(get_aqi_category(50), "Good")

    def test_moderate(self):
        self.assertEqual(get_aqi_category(51), "Moderate")
        self.assertEqual(get_aqi_category(100), "Moderate")

    def test_sensitive(self):
        self.assertEqual(get_aqi_category(101), "Unhealthy for Sensitive Groups")
        self.assertEqual(get_aqi_category(150), "Unhealthy for Sensitive Groups")

    def test_unhealthy(self):
        self.assertEqual(get_aqi_category(151), "Unhealthy")
        self.assertEqual(get_aqi_category(200), "Unhealthy")

    def test_very_unhealthy(self):
        self.assertEqual(get_aqi_category(201), "Very Unhealthy")
        self.assertEqual(get_aqi_category(300), "Very Unhealthy")

    def test_hazardous(self):
        self.assertEqual(get_aqi_category(301), "Hazardous")
        self.assertEqual(get_aqi_category(500), "Hazardous")

    def test_rich_flag_adds_markup(self):
        result = get_aqi_category(25, rich=True)
        self.assertIn("[green]", result)
        self.assertIn("Good", result)

    def test_string_input(self):
        """AQI can arrive as a string from the API JSON."""
        self.assertEqual(get_aqi_category("45"), "Good")


# ---------------------------------------------------------------------------
# safe_get
# ---------------------------------------------------------------------------
from main import safe_get  # noqa: E402


class TestSafeGet(unittest.TestCase):
    def test_nested_hit(self):
        d = {"a": {"b": {"c": 42}}}
        self.assertEqual(safe_get(d, "a", "b", "c"), 42)

    def test_missing_key_returns_default(self):
        d = {"a": {"b": 1}}
        self.assertEqual(safe_get(d, "a", "x"), "N/A")

    def test_custom_default(self):
        self.assertEqual(safe_get({}, "missing", default=0), 0)

    def test_non_dict_in_chain(self):
        d = {"a": "not_a_dict"}
        self.assertEqual(safe_get(d, "a", "b"), "N/A")


# ---------------------------------------------------------------------------
# geocode_location
# ---------------------------------------------------------------------------
from geocode_location import geocode_location  # noqa: E402


class TestGeocodeLocation(unittest.TestCase):
    def _mock_response(self, data):
        mock = MagicMock()
        mock.json.return_value = data
        mock.raise_for_status.return_value = None
        return mock

    @patch("geocode_location.requests.get")
    def test_returns_lat_lon(self, mock_get):
        mock_get.return_value = self._mock_response(
            [{"lat": "37.7749", "lon": "-122.4194"}]
        )
        lat, lon = geocode_location("San Francisco, CA")
        self.assertAlmostEqual(lat, 37.7749)
        self.assertAlmostEqual(lon, -122.4194)

    @patch("geocode_location.requests.get")
    def test_empty_result_raises(self, mock_get):
        mock_get.return_value = self._mock_response([])
        with self.assertRaises(ValueError):
            geocode_location("nowhere land xyzzy")

    @patch("geocode_location.requests.get")
    def test_correct_user_agent_sent(self, mock_get):
        mock_get.return_value = self._mock_response(
            [{"lat": "0", "lon": "0"}]
        )
        geocode_location("Tokyo")
        _, kwargs = mock_get.call_args
        self.assertIn("User-Agent", kwargs["headers"])


# ---------------------------------------------------------------------------
# get_json retry logic
# ---------------------------------------------------------------------------
from main import get_json  # noqa: E402
import requests as req_lib


class TestGetJson(unittest.TestCase):
    @patch("main.session")
    def test_returns_json_on_success(self, mock_session):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None
        mock_session.get.return_value = mock_resp
        result = get_json("http://example.com")
        self.assertEqual(result, {"ok": True})

    @patch("main.time.sleep", return_value=None)
    @patch("main.session")
    def test_retries_on_timeout(self, mock_session, _sleep):
        mock_session.get.side_effect = req_lib.Timeout
        with self.assertRaises(req_lib.Timeout):
            get_json("http://example.com", retries=3)
        self.assertEqual(mock_session.get.call_count, 3)


if __name__ == "__main__":
    unittest.main()
