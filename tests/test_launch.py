from unittest.mock import Mock, patch

import launch


def test_existing_server_opens_without_starting_another():
    with patch.object(launch, "healthy", return_value=True), \
         patch.object(launch.webbrowser, "open") as browser, \
         patch.object(launch.subprocess, "Popen") as start:
        assert launch.main() == 0
        browser.assert_called_once_with(launch.URL)
        start.assert_not_called()


def test_starts_server_when_absent(tmp_path):
    process = Mock(pid=123)
    with patch.object(launch, "ROOT", tmp_path), \
         patch.object(launch, "healthy", side_effect=[False, True]), \
         patch.object(launch.webbrowser, "open") as browser, \
         patch.object(launch.subprocess, "Popen", return_value=process) as start:
        assert launch.main() == 0
        browser.assert_called_once_with(launch.URL)
        assert (tmp_path / "work/server.pid").read_text() == "123"
        assert "--server.headless" in start.call_args.args[0]
