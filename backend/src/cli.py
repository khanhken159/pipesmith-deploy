"""Giao diện dòng lệnh (giai đoạn A): `python -m src.cli <lệnh>`.

Dùng argparse (thư viện chuẩn, không thêm dependency; đủ cho vài lệnh con).
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.config import get_settings
from src.logging_config import setup_logging
from src.services.tracing import configure_tracing

ROLES = ("de", "engineer", "reviewer")  # mặc định `de`; engineer/reviewer khi bật REQUIRE_SEPARATE_REVIEWER


def _add_identity(parser: argparse.ArgumentParser, default_role: str) -> None:
    parser.add_argument("--as", dest="role", choices=ROLES, default=default_role, help="Vai trò")
    parser.add_argument(
        "--user", default=os.environ.get("USERNAME") or os.environ.get("USER") or "engineer", help="Tên người dùng"
    )


def _run_parsers(sub: argparse._SubParsersAction) -> None:
    run = sub.add_parser("run", help="Chạy luồng từ yêu cầu bằng lời")
    run.add_argument(
        "--request", required=True, help="Yêu cầu nghiệp vụ, ví dụ: gộp đơn hàng 3 nguồn, tính doanh thu ngày"
    )
    run.add_argument("--auto-answer", action="store_true", help="Tự chọn đáp án đầu tiên ở J1 (chỉ dùng cho test/demo)")
    run.add_argument("--auto-approve", action="store_true", help="Tự duyệt ở J2 (CHỈ dùng cho test/eval)")
    _add_identity(run, "de")
    review = sub.add_parser("review", help="Xem diff, bằng chứng và duyệt")
    review.add_argument("run_id", help="id lần chạy, hoặc `latest`")
    review.add_argument("--approve", action="store_true")
    review.add_argument("--reject", action="store_true")
    review.add_argument("--note", default="", help="Ghi chú khi từ chối")
    review.add_argument("--full", action="store_true", help="Hiện toàn bộ nội dung file")
    _add_identity(review, "de")
    answer = sub.add_parser("answer", help="Trả lời câu hỏi làm rõ của một lần chạy đang chờ")
    answer.add_argument("run_id")
    _add_identity(answer, "de")


def build_parser() -> argparse.ArgumentParser:
    """Khai báo các lệnh con."""
    parser = argparse.ArgumentParser(
        prog="python -m src.cli", description="P-113: agent sinh & tối ưu pipeline ELT/ETL"
    )
    parser.add_argument("--provider", choices=("mock", "openai", "google"), help="Ghi đè LLM_PROVIDER")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Kiểm tra môi trường")
    seed = sub.add_parser("seed", help="Sinh dữ liệu giả lập đa nguồn vào data/sources")
    seed.add_argument("--dirty", type=float, default=0.05, help="Mức bẩn 0..0.5")
    seed.add_argument("--rows", type=int, default=300, help="Số đơn mỗi nguồn")
    seed.add_argument(
        "--profile",
        choices=("company", "basic"),
        default="company",
        help="company: kho raw cả công ty (19 bảng, 8 hệ thống); basic: chỉ 3 nguồn đơn online",
    )
    seed.add_argument("--scale", type=float, default=1.0, help="Hệ số quy mô bộ company (0.2 = nhỏ, 3 = lớn)")
    _run_parsers(sub)
    status = sub.add_parser("status", help="Xem trạng thái (bỏ trống id để xem danh sách)")
    status.add_argument("run_id", nargs="?")
    errors = sub.add_parser("errors", help="Sổ lỗi: liệt kê, duyệt, bỏ")
    errors.add_argument("--approve", type=int, metavar="ID")
    errors.add_argument("--fix", default="", help="Cách sửa (khi duyệt)")
    errors.add_argument("--discard", type=int, metavar="ID")
    _add_identity(errors, "de")
    optimize = sub.add_parser("optimize", help="Chạy riêng E4 + V3 cho một file SQL")
    optimize.add_argument("--sql", required=True, type=Path)
    optimize.add_argument("--dataset", default="large", help="Bộ dữ liệu để đo tốc độ")
    optimize.add_argument("--run", dest="run_id", help="Lấy bộ dữ liệu thử của lần chạy này (mặc định: mới nhất)")
    evaluate = sub.add_parser("eval", help="Chạy bộ đánh giá (golden, mutation, pytest) → eval/results/report.md")
    evaluate.add_argument("--with-llm", action="store_true", help="Chạy thêm golden bằng LLM thật (tốn token)")
    return parser


def configure(args: argparse.Namespace) -> None:
    """UTF-8 cho terminal Windows, nạp .env, ghi đè provider, log gọn."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    load_dotenv()
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    get_settings.cache_clear()
    setup_logging("WARNING")
    warning = configure_tracing()
    if warning:
        print(f"! {warning}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Điểm vào CLI; trả mã thoát."""
    args = build_parser().parse_args(argv)
    configure(args)
    from src.cli_commands import COMMANDS

    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
