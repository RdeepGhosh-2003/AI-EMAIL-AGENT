import unittest
from unittest.mock import patch
from io import BytesIO

import launch_dashboard


class Response(BytesIO):
    def __init__(self, status):
        super().__init__(b"{}")
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class DashboardLauncherTests(unittest.TestCase):
    @patch.object(launch_dashboard.urllib.request, "urlopen", return_value=Response(200))
    def test_ready_check_uses_auth_status_so_pin_lock_counts_as_ready(self, urlopen):
        self.assertTrue(launch_dashboard.dashboard_is_ready("http://localhost:5001"))
        urlopen.assert_called_once_with("http://localhost:5001/api/auth/status", timeout=1)

    @patch.object(launch_dashboard.webbrowser, "open")
    @patch.object(launch_dashboard, "start_agent")
    @patch.object(launch_dashboard, "dashboard_is_ready", return_value=True)
    @patch.object(launch_dashboard, "dashboard_url", return_value="http://localhost:5001")
    def test_running_agent_only_opens_browser(self, dashboard_url, is_ready, start_agent, open_browser):
        self.assertEqual(launch_dashboard.main(), 0)
        start_agent.assert_not_called()
        open_browser.assert_called_once_with("http://localhost:5001", new=2)

    @patch.object(launch_dashboard.time, "sleep")
    @patch.object(launch_dashboard.webbrowser, "open")
    @patch.object(launch_dashboard, "start_agent")
    @patch.object(launch_dashboard, "dashboard_is_ready", side_effect=[False, False, True])
    @patch.object(launch_dashboard, "dashboard_url", return_value="http://localhost:5001")
    def test_stopped_agent_is_started_before_browser_opens(
        self, dashboard_url, is_ready, start_agent, open_browser, sleep
    ):
        self.assertEqual(launch_dashboard.main(), 0)
        start_agent.assert_called_once_with()
        open_browser.assert_called_once_with("http://localhost:5001", new=2)


if __name__ == "__main__":
    unittest.main()
