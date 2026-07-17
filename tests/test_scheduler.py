import plistlib
import sys
from unittest.mock import MagicMock

import pytest

from trakt_calendar_sync import scheduler
from trakt_calendar_sync.scheduler import linux as linux_backend
from trakt_calendar_sync.scheduler import macos as macos_backend
from trakt_calendar_sync.scheduler import windows as windows_backend


def test_sync_command_dev_mode(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert scheduler.sync_command() == [sys.executable, "-m", "trakt_calendar_sync.cli_sync"]


def test_sync_command_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert scheduler.sync_command() == [sys.executable, "--sync"]


def test_backend_dispatches_by_platform(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "linux")
    assert scheduler._backend() is linux_backend
    monkeypatch.setattr(scheduler.sys, "platform", "darwin")
    assert scheduler._backend() is macos_backend
    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    assert scheduler._backend() is windows_backend


def test_backend_raises_for_unsupported_platform(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "freebsd13")

    with pytest.raises(RuntimeError):
        scheduler._backend()


# --- linux (systemd --user) ---


def test_linux_enable_writes_units_and_calls_systemctl(monkeypatch, tmp_path):
    service_path = tmp_path / "trakt-calendar-sync.service"
    timer_path = tmp_path / "trakt-calendar-sync.timer"
    monkeypatch.setattr(linux_backend, "SYSTEMD_USER_DIR", tmp_path)
    monkeypatch.setattr(linux_backend, "SERVICE_PATH", service_path)
    monkeypatch.setattr(linux_backend, "TIMER_PATH", timer_path)
    run = MagicMock()
    monkeypatch.setattr(linux_backend.subprocess, "run", run)

    linux_backend.enable(["/usr/bin/trakt-calendar-sync-cli"], 9, 30)

    assert "ExecStart=/usr/bin/trakt-calendar-sync-cli" in service_path.read_text()
    assert "OnCalendar=*-*-* 09:30:00" in timer_path.read_text()
    assert run.call_args_list[0].args[0] == ["systemctl", "--user", "daemon-reload"]
    assert run.call_args_list[1].args[0] == [
        "systemctl",
        "--user",
        "enable",
        "--now",
        "trakt-calendar-sync.timer",
    ]


def test_linux_enable_quotes_command_parts_with_spaces(monkeypatch, tmp_path):
    service_path = tmp_path / "s.service"
    monkeypatch.setattr(linux_backend, "SYSTEMD_USER_DIR", tmp_path)
    monkeypatch.setattr(linux_backend, "SERVICE_PATH", service_path)
    monkeypatch.setattr(linux_backend, "TIMER_PATH", tmp_path / "s.timer")
    monkeypatch.setattr(linux_backend.subprocess, "run", MagicMock())

    linux_backend.enable(["/path with spaces/app", "--sync"], 0, 0)

    assert "ExecStart='/path with spaces/app' --sync" in service_path.read_text()


def test_linux_disable_removes_units(monkeypatch, tmp_path):
    service_path = tmp_path / "s.service"
    timer_path = tmp_path / "s.timer"
    service_path.write_text("x")
    timer_path.write_text("x")
    monkeypatch.setattr(linux_backend, "SERVICE_PATH", service_path)
    monkeypatch.setattr(linux_backend, "TIMER_PATH", timer_path)
    monkeypatch.setattr(linux_backend.subprocess, "run", MagicMock())

    linux_backend.disable()

    assert not service_path.exists()
    assert not timer_path.exists()


def test_linux_is_enabled_true(monkeypatch):
    monkeypatch.setattr(
        linux_backend.subprocess, "run", MagicMock(return_value=MagicMock(stdout="enabled\n"))
    )
    assert linux_backend.is_enabled() is True


def test_linux_is_enabled_false(monkeypatch):
    monkeypatch.setattr(
        linux_backend.subprocess, "run", MagicMock(return_value=MagicMock(stdout="disabled\n"))
    )
    assert linux_backend.is_enabled() is False


# --- macos (launchd) ---


def test_macos_enable_writes_plist_and_loads(monkeypatch, tmp_path):
    plist_path = tmp_path / "com.traktcalendarsync.sync.plist"
    monkeypatch.setattr(macos_backend, "PLIST_PATH", plist_path)
    monkeypatch.setattr(macos_backend, "LOG_PATH", tmp_path / "log.log")
    run = MagicMock()
    monkeypatch.setattr(macos_backend.subprocess, "run", run)

    macos_backend.enable(["/usr/local/bin/app", "--sync"], 8, 15)

    data = plistlib.loads(plist_path.read_bytes())
    assert data["ProgramArguments"] == ["/usr/local/bin/app", "--sync"]
    assert data["StartCalendarInterval"] == {"Hour": 8, "Minute": 15}
    load_calls = [c for c in run.call_args_list if c.args[0][:2] == ["launchctl", "load"]]
    assert len(load_calls) == 1
    assert load_calls[0].args[0] == ["launchctl", "load", "-w", str(plist_path)]


def test_macos_disable_unloads_and_removes_plist(monkeypatch, tmp_path):
    plist_path = tmp_path / "p.plist"
    plist_path.write_text("x")
    monkeypatch.setattr(macos_backend, "PLIST_PATH", plist_path)
    monkeypatch.setattr(macos_backend.subprocess, "run", MagicMock())

    macos_backend.disable()

    assert not plist_path.exists()


def test_macos_is_enabled_false_when_no_plist(monkeypatch, tmp_path):
    monkeypatch.setattr(macos_backend, "PLIST_PATH", tmp_path / "missing.plist")

    assert macos_backend.is_enabled() is False


def test_macos_is_enabled_true_when_loaded(monkeypatch, tmp_path):
    plist_path = tmp_path / "p.plist"
    plist_path.write_text("x")
    monkeypatch.setattr(macos_backend, "PLIST_PATH", plist_path)
    monkeypatch.setattr(
        macos_backend.subprocess, "run", MagicMock(return_value=MagicMock(returncode=0))
    )

    assert macos_backend.is_enabled() is True


# --- windows (Task Scheduler) ---


def test_windows_enable_calls_schtasks_create(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(windows_backend.subprocess, "run", run)

    windows_backend.enable(["C:\\Program Files\\app.exe", "--sync"], 7, 5)

    args = run.call_args.args[0]
    assert args[:3] == ["schtasks", "/create", "/tn"]
    assert windows_backend.TASK_NAME in args
    assert "/st" in args
    assert "07:05" in args


def test_windows_disable_calls_schtasks_delete(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(windows_backend.subprocess, "run", run)

    windows_backend.disable()

    run.assert_called_once()
    assert run.call_args.args[0][:3] == ["schtasks", "/delete", "/tn"]


def test_windows_is_enabled_true_when_query_succeeds(monkeypatch):
    monkeypatch.setattr(
        windows_backend.subprocess, "run", MagicMock(return_value=MagicMock(returncode=0))
    )
    assert windows_backend.is_enabled() is True


def test_windows_is_enabled_false_when_query_fails(monkeypatch):
    monkeypatch.setattr(
        windows_backend.subprocess, "run", MagicMock(return_value=MagicMock(returncode=1))
    )
    assert windows_backend.is_enabled() is False
