"""Ước tính chi phí gọi LLM theo bảng giá công khai (USD / 1 triệu token).

Giá chỉ là ước tính để so sánh; kiểm tra lại trang giá của nhà cung cấp trước khi báo cáo.
"""

# Giá chuẩn (ngữ cảnh ≤200k), đối chiếu trang giá chính thức OpenAI và Google ngày 2026-10-02.
PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (4.00, 20.00),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Chi phí ước tính; model không có trong bảng giá thì trả 0.0."""
    price_in, price_out = PRICES_PER_MILLION.get(model, (0.0, 0.0))
    return round((input_tokens * price_in + output_tokens * price_out) / 1_000_000, 6)


def compute_cost_usd(seconds: float, cost_per_hour_usd: float) -> float:
    """Quy đổi thời gian máy chạy query thành tiền (dùng cho cổng hòa vốn của optimizer)."""
    return seconds / 3600 * cost_per_hour_usd
