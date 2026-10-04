from unittest.mock import Mock, patch

import launch


def test_current_server_is_reused(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work/server.code").write_text("same")
    with patch.object(launch, "ROOT", tmp_path), \
         patch.object(launch, "code_fingerprint", return_value="same"), \
         patch.object(launch, "healthy", return_value=True), \
         patch.object(launch.webbrowser, "open") as browser, \
         patch.object(launch.subprocess, "Popen") as start:
        assert launch.main() == 0
        browser.assert_called_once_with(launch.URL)
        start.assert_not_called()


def test_starts_server_when_absent(tmp_path):
    process = Mock(pid=123)
    with patch.object(launch, "ROOT", tmp_path), \
         patch.object(launch, "code_fingerprint", return_value="abc"), \
         patch.object(launch, "healthy", side_effect=[False, True]), \
         patch.object(launch.webbrowser, "open") as browser, \
         patch.object(launch.subprocess, "Popen", return_value=process) as start:
        assert launch.main() == 0
        browser.assert_called_once_with(launch.URL)
        assert (tmp_path / "work/server.pid").read_text() == "123"
        assert (tmp_path / "work/server.code").read_text() == "abc"
        assert "--server.headless" in start.call_args.args[0]


def test_outdated_own_server_is_restarted(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work/server.code").write_text("old")
    (tmp_path / "work/server.pid").write_text("41")
    with patch.object(launch, "ROOT", tmp_path), \
         patch.object(launch, "code_fingerprint", return_value="new"), \
         patch.object(launch, "healthy", side_effect=[True, False, True]), \
         patch.object(launch.os, "kill") as kill, \
         patch.object(launch.webbrowser, "open"), \
         patch.object(launch.subprocess, "Popen", return_value=Mock(pid=42)):
        assert launch.main() == 0
        kill.assert_called_once_with(41, launch.signal.SIGTERM)
        assert (tmp_path / "work/server.code").read_text() == "new"


def test_unknown_server_on_port_is_left_alone(tmp_path):
    with patch.object(launch, "ROOT", tmp_path), \
         patch.object(launch, "code_fingerprint", return_value="new"), \
         patch.object(launch, "healthy", return_value=True), \
         patch.object(launch.os, "kill") as kill, \
         patch.object(launch.subprocess, "Popen") as start:
        assert launch.main() == 1
        kill.assert_not_called()
        start.assert_not_called()


def test_fingerprint_changes_with_package_code():
    assert launch.code_fingerprint() == launch.code_fingerprint()
    assert len(launch.code_fingerprint()) == 64


def test_failed_start_shows_the_log(tmp_path, capsys):
    def crash(*args, stdout, **kwargs):
        stdout.write("ModuleNotFoundError: streamlit\n")
        return Mock(poll=Mock(return_value=1))

    with patch.object(launch, "ROOT", tmp_path), \
         patch.object(launch, "code_fingerprint", return_value="abc"), \
         patch.object(launch, "healthy", return_value=False), \
         patch.object(launch.subprocess, "Popen", side_effect=crash):
        assert launch.main() == 1
    assert "ModuleNotFoundError: streamlit" in capsys.readouterr().out
    assert not (tmp_path / "work/server.pid").exists()


def test_health_check_needs_an_ok_reply():
    reply = Mock(status=200, read=Mock(return_value=b"ok\n"))
    with patch.object(launch.urllib.request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value = reply
        assert launch.healthy()
        reply.read.return_value = b"starting"
        assert not launch.healthy()
        urlopen.side_effect = OSError("refused")
        assert not launch.healthy()
