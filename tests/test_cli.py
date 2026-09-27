import pytest

from surfdeck import cli, surf as surf_mod
from surfdeck.spots import DEFAULT_SPOT


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path, report):
    """Never touch the network in CLI tests."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(surf_mod, "fetch_report", lambda spot, timeout=8.0: report)


def test_list_spots(capsys):
    assert cli.main(["--list-spots"]) == 0
    out = capsys.readouterr().out
    assert "south-beach" in out and "South Beach, FL" in out
    assert out.splitlines()[0].startswith("*")  # the default is marked


def test_unknown_spot_is_a_usage_error(capsys):
    assert cli.main(["--spot", "mars"]) == 2
    assert "unknown spot" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert "surfdeck" in capsys.readouterr().out


def test_once_prints_a_full_report(capsys):
    assert cli.main(["--once", "--no-color", "--width", "90", "--no-scene"]) == 0
    out = capsys.readouterr().out
    assert "SOUTH BEACH, FL" in out
    assert "WAVE" in out and "SWELL" in out and "WIND" in out
    assert "SHIP'S SYSTEMS" in out
    assert "PID" in out
    assert "\033[" not in out


def test_once_reports_failure_with_exit_code_one(monkeypatch, capsys, report):
    def offline_fetch(spot, timeout=8.0):
        broken = surf_mod.SurfReport(spot.key, spot.name, spot.facing_deg)
        broken.error = "no signal"
        return broken

    monkeypatch.setattr(surf_mod, "fetch_report", offline_fetch)
    assert cli.main(["--once", "--no-color", "--no-scene"]) == 1
    assert "OFFLINE" in capsys.readouterr().out


def test_no_color_env_var_is_respected(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    cli.main(["--once", "--width", "80", "--no-scene"])
    assert "\033[" not in capsys.readouterr().out


def test_interactive_mode_refuses_a_pipe(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False, raising=False)
    assert cli.main([]) == 2
    assert "needs a terminal" in capsys.readouterr().err


def test_defaults(capsys):
    args = cli.build_parser().parse_args([])
    assert args.spot == DEFAULT_SPOT
    assert args.theme == "pirate"
    assert args.units == "imperial"
    assert args.fps == 12
