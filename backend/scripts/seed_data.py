"""Sinh dữ liệu đơn hàng giả lập vào data/sources/. Tương đương `python -m src.cli seed`."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.services.seed import SeedConfig, generate_sources  # noqa: E402


def main() -> None:
    """Đọc tham số dòng lệnh và sinh dữ liệu."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dirty", type=float, default=0.05, help="Mức bẩn 0..0.5 (mặc định 0.05)")
    parser.add_argument("--rows", type=int, default=300, help="Số đơn mỗi nguồn")
    args = parser.parse_args()
    settings = get_settings()
    cfg = SeedConfig(out_dir=settings.sources_dir, seed=settings.seed, dirty=args.dirty, rows_per_source=args.rows)
    for name, count in generate_sources(cfg).items():
        print(f"{name}: {count} dòng")


if __name__ == "__main__":
    main()
