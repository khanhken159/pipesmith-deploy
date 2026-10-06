"""Test giao diện dòng lệnh (gọi `main([...])` trực tiếp)."""

from pathlib import Path

import pytest

from src.cli import build_parser, main
from src.services.store import get_store


@pytest.mark.parametrize(
    "argv",
    [
        ["doctor"],
        ["seed"],
        ["run", "--request", "x"],
        ["answer", "r1"],
        ["review", "r1"],
        ["status"],
        ["errors"],
        ["optimize", "--sql", "a.sql"],
    ],
)
def test_parser_has_all_commands(argv: list[str]):
    assert build_parser().parse_args(argv).command == argv[0]


def test_doctor_and_seed(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert main(["doctor"]) == 0
    monkeypatch.setenv("SOURCES_DIR", str(tmp_path / "src"))
    assert main(["seed", "--rows", "20"]) == 0
    assert (tmp_path / "src" / "shopee_orders.csv").exists()
    out = capsys.readouterr().out.replace("\n", "")  # rich có thể xuống dòng giữa đường dẫn dài
    assert "Python" in out and "shopee_orders.csv" in out


def test_reviewer_role_cannot_create_request_in_separate_mode(capsys, separate_reviewer):
    assert main(["run", "--request", "x", "--as", "reviewer"]) == 2
    assert "Reviewer" in capsys.readouterr().out


def test_status_and_errors_listing(capsys):
    record = get_store().create_run("doanh thu", "alice")
    assert main(["status"]) == 0
    assert main(["status", record.id]) == 0
    assert main(["status", "khong-co"]) == 1
    assert main(["errors"]) == 0


def test_errors_approve_needs_reviewer_only_in_separate_mode(separate_reviewer):
    assert main(["errors", "--approve", "1", "--as", "engineer"]) == 2


def test_review_blocks_requester_and_wrong_role(capsys, separate_reviewer):
    record = get_store().create_run("doanh thu", "alice")
    assert main(["review", record.id, "--as", "reviewer", "--user", "alice"]) == 2
    assert main(["review", record.id, "--as", "engineer", "--user", "bob"]) == 2
    assert "không được tự duyệt" in capsys.readouterr().out


def test_optimize_without_datasets(tmp_path: Path, capsys):
    sql = tmp_path / "q.sql"
    sql.write_text("select 1", encoding="utf-8")
    assert main(["optimize", "--sql", str(sql), "--run", "khong-co"]) == 1


@pytest.mark.slow
def test_run_end_to_end_with_auto_approve(built_state, capsys):
    assert (
        main(
            [
                "--provider",
                "mock",
                "run",
                "--request",
                "Gộp đơn 3 nguồn, doanh thu ngày",
                "--user",
                "erin",
                "--auto-approve",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Chế độ mô phỏng" in out and "đã duyệt" in out
    latest = get_store().list_runs(1)[0]
    assert latest.status == "approved" and latest.requester == "erin"


def test_eval_command_is_registered():
    from src.cli import build_parser
    from src.cli_commands import COMMANDS

    args = build_parser().parse_args(["eval", "--with-llm"])
    assert args.command == "eval" and args.with_llm is True and "eval" in COMMANDS
