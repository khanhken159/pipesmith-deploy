"""Chạy bộ đánh giá và ghi eval/results/report.md (chỉ số đo thật; chưa đo thì ghi "—").

Mặc định chỉ chạy phần KHÔNG cần LLM (chạy được trong CI, không tốn tiền):
  pytest + độ phủ, golden `reference` (kiểm chứng kết quả đúng), mutation test (bộ kiểm chứng bắt lỗi giả).
Thêm `--with-llm` để chạy golden `agent` bằng LLM đang cấu hình (tốn token; ghi rõ provider/model).

    python eval/run_eval.py               # hoặc: make eval
    python eval/run_eval.py --with-llm
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
PY = sys.executable

# Bảng truy vết test → tính năng (CLAUDE.md mục 8)
TRACE = [
    ("tests/test_verifiers/test_spec_check.py", "V0 Soát đặc tả: chặn khi còn điểm chưa rõ, grain sai, mode sai"),
    ("tests/test_verifiers/test_data_nodes.py", "E0 Nhận nguồn, P Soi dữ liệu (định dạng ngày/tiền), E2 Dữ liệu thử"),
    ("tests/test_verifiers/test_sql_tools.py", "V1: chặn lệnh nguy hiểm, đường dẫn ngoài sandbox, bảng/cột bịa"),
    ("tests/test_verifiers/test_safety_and_sandbox.py", "V1 An toàn + V2 Sandbox (dbt build thật, bắt SUM→AVG)"),
    ("tests/test_agents/test_llm_nodes.py", "E1 Planner, E3 Codegen, E3b Testgen mù code"),
    ("tests/test_agents/test_fix_loop.py", "Vòng sửa E3 ↔ V1/V2: lỗi gốc, gợi ý cột, biên dịch thử, chặn hỏi lặp"),
    ("tests/test_agents/test_routing.py", "Rẽ nhánh graph (vòng sửa ≤3, cứu hộ, giới hạn vòng)"),
    ("tests/test_agents/test_graph.py", "Graph end-to-end: J1 → J2, duyệt/từ chối, quyền, cứu hộ"),
    ("tests/test_optimizer/", "E4 Optimizer + V3 Đối chiếu (applied / skipped / loại vì lệch)"),
    ("tests/test_services/test_llm.py", "Cổng LLM: mock/openai/google, model theo bước, dự phòng Gemini"),
    ("tests/test_services/test_store_and_memory.py", "Kho lần chạy + sổ lỗi cần duyệt"),
    ("tests/test_cli/test_cli.py", "CLI: doctor, seed, run, review, errors, optimize"),
    ("tests/test_api/test_routes.py", "API: /health, danh sách lần chạy"),
    ("tests/test_eval/", "Bộ chấm ELT-Bench, golden (khớp SQL chuẩn), đột biến áp dụng được"),
]


def run_step(args: list[str]) -> str:
    """Chạy một bước (tiến trình con), in và trả về đầu ra."""
    print("→", " ".join(args[1:]), flush=True)
    done = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = done.stdout + done.stderr
    print(output[-1500:], flush=True)
    return output


def pytest_summary(output: str) -> dict:
    """Số test đạt/lỗi và độ phủ từ đầu ra pytest."""
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    coverage = re.search(r"Total coverage: ([\d.]+)%", output)
    return {
        "passed": int(passed.group(1)) if passed else None,
        "failed": int(failed.group(1)) if failed else 0,
        "coverage_pct": float(coverage.group(1)) if coverage else None,
    }


def load(name: str) -> dict | None:
    """Đọc eval/results/<name>.json nếu có."""
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _fmt(value: object, suffix: str = "") -> str:
    return "—" if value is None else f"{value}{suffix}"


def golden_lines(reference: dict | None, agent: dict | None) -> list[str]:
    """Dòng bảng chỉ số cho bộ golden."""
    ref_rows = reference["rows"] if reference else []
    lines = [
        f"| Golden: kết quả đúng khớp SQL chuẩn | code | {_fmt(sum(r['ok'] for r in ref_rows) if ref_rows else None)}"
        f"/{len(ref_rows) or '—'} ca |"
    ]
    rows = agent["rows"] if agent else []
    if not rows:
        return lines + ["| Golden: agent đúng so với kết quả đúng | — | — (chưa chạy với LLM thật) |"]
    who = f"{agent['provider']}/{agent['model']}"
    first_pass = sum(r["v_failures"] == 0 and r["ok"] for r in rows)
    return lines + [
        f"| Golden: agent đúng so với kết quả đúng | {who} | {sum(r['ok'] for r in rows)}/{len(rows)} ca |",
        f"| Golden: đạt ngay lần đầu (0 lỗi V1/V2) | {who} | {first_pass}/{len(rows)} ca |",
        f"| Golden: chọn đúng mode ELT/ETL | {who} | {sum(r['mode_ok'] for r in rows)}/{len(rows)} ca |",
        f"| Golden: token / chi phí trung bình mỗi ca | {who} | {sum(r['tokens'] for r in rows) // len(rows)} token / "
        f"{round(sum(r['cost_usd'] for r in rows) / len(rows), 4)} USD |",
        f"| Golden: thời gian trung bình yêu cầu → bản duyệt | {who} | {round(sum(r['seconds'] for r in rows) / len(rows), 1)} s |",
    ]


def metric_lines(tests: dict, mutation: dict | None) -> list[str]:
    """Bảng chỉ số chính."""
    m = mutation["summary"] if mutation else {}
    return [
        "| Chỉ số | Provider/model | Kết quả |",
        "|---|---|---|",
        f"| pytest | mock (không cần khóa) | {_fmt(tests.get('passed'))} đạt, {tests.get('failed', 0)} lỗi |",
        f"| Độ phủ code | — | {_fmt(tests.get('coverage_pct'), '%')} (ngưỡng 60%) |",
        f"| Mutation: bắt được lỗi giả | code (0 token) | {_fmt(m.get('real_caught'))}/{_fmt(m.get('real_total'))} "
        f"({_fmt(m.get('kill_rate_pct'), '%')}) |",
        f"| Mutation: báo động nhầm ở đối chứng | code (0 token) | {_fmt(m.get('false_alarms'))}/{_fmt(m.get('controls_total'))} |",
    ]


def eltbench_line() -> list[str]:
    """Dòng ELT-Bench (agent) đọc từ eltbench_agent.md nếu đã chạy bằng LLM thật."""
    path = RESULTS / "eltbench_agent.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    score, who = re.search(r"Khớp bảng kết quả đúng: (\d+/\d+)", text), re.search(r"provider/model: (.+)", text)
    if not score or not who:
        return ["| ELT-Bench-Verified (10 task, 34 bảng): khớp bảng đúng | — | — (chưa chạy với LLM thật) |"]
    return [f"| ELT-Bench-Verified (10 task, 34 bảng): khớp bảng đúng | {who.group(1)} | {score.group(1)} bảng |"]


def write_report(tests: dict) -> None:
    """Ghi eval/results/report.md từ các file kết quả đã có."""
    golden = golden_lines(load("golden_reference"), load("golden_agent"))
    lines = [
        "# Evaluation Report — P-113",
        "",
        f"> Sinh tự động bởi `eval/run_eval.py` ngày {date.today().isoformat()}. Chỉ ghi số đã đo thật; chưa đo ghi `—`.",
        "> Số chạy bằng `mock` KHÔNG phải chất lượng mô hình thật.",
        "",
        "## 1. Chỉ số",
        "",
        *metric_lines(tests, load("mutation")),
        *golden,
        *eltbench_line(),
        "",
        "Chi tiết: [mutation.md](mutation.md) • [golden_reference.md](golden_reference.md) • "
        "[golden_agent.md](golden_agent.md) • [eltbench_reference.md](eltbench_reference.md) • "
        "[eltbench_agent.md](eltbench_agent.md) • [tpch_benchmark.md](tpch_benchmark.md)",
        "",
        "## 2. Thời gian phản hồi API",
        "",
        "— (đo ở Phase 7 khi có đủ endpoint).",
        "",
        "## 3. Phản hồi người dùng thử",
        "",
        "— (chưa thu thập; cần 3–5 người).",
        "",
        "## 4. Truy vết test → tính năng",
        "",
        "| Test | Tính năng |",
        "|---|---|",
        *[f"| `{path}` | {feature} |" for path, feature in TRACE],
    ]
    (RESULTS / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Đã ghi {RESULTS / 'report.md'}")


def main() -> None:
    """Chạy các bước đánh giá rồi ghi báo cáo."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-llm", action="store_true", help="Chạy thêm golden bằng LLM thật (tốn token)")
    parser.add_argument("--skip-tests", action="store_true", help="Bỏ qua pytest (chỉ gom kết quả)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    tests = {} if args.skip_tests else pytest_summary(run_step([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"]))
    run_step([PY, "eval/golden/run_golden.py", "--mode", "reference"])
    run_step([PY, "eval/mutation/run_mutation.py"])
    if args.with_llm:
        run_step([PY, "eval/golden/run_golden.py", "--mode", "agent"])
    write_report(tests)


if __name__ == "__main__":
    main()
