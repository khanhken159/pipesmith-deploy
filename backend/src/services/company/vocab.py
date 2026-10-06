"""Từ vựng cho công ty bán lẻ giả lập "P113 Retail": tên người, địa danh, danh mục hàng, thương hiệu.

Thương hiệu là tên chung chung tự đặt, không dùng tên công ty thật.
"""

COMPANY = "P113 Retail (công ty giả lập)"

LAST_NAMES = ("Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô")
MIDDLE_NAMES = ("Văn", "Thị", "Minh", "Ngọc", "Thanh", "Đức", "Hoàng", "Gia", "Anh", "Thu", "Quốc", "Bảo")
FIRST_NAMES = (
    "An", "Bình", "Châu", "Dũng", "Giang", "Hà", "Hải", "Hạnh", "Hiếu", "Hoa", "Hùng", "Hương", "Khánh", "Lan",
    "Linh", "Long", "Mai", "Nam", "Ngân", "Phong", "Phúc", "Quân", "Quỳnh", "Sơn", "Tâm", "Thảo", "Trang", "Trung",
    "Tú", "Tuấn", "Vy", "Yến",
)  # fmt: skip

CITIES = {
    "Hà Nội": "Bắc",
    "Hải Phòng": "Bắc",
    "Đà Nẵng": "Trung",
    "Huế": "Trung",
    "Nha Trang": "Trung",
    "TP. Hồ Chí Minh": "Nam",
    "Cần Thơ": "Nam",
    "Biên Hòa": "Nam",
    "Vũng Tàu": "Nam",
}
CITY_VARIANTS = {
    "TP. Hồ Chí Minh": ["HCM", "Ho Chi Minh", "tp hcm", "Sài Gòn", "TPHCM", "Hồ Chí Minh"],
    "Hà Nội": ["HN", "Ha Noi", "hà nội", "Hanoi"],
    "Đà Nẵng": ["Da Nang", "DN", "đà nẵng"],
    "Cần Thơ": ["Can Tho", "cần thơ"],
}

CATEGORIES = {
    "Điện thoại": (("Novaphone", "Aurora", "Kite"), (2_500_000, 25_000_000)),
    "Laptop": (("Novabook", "Lumen", "Orbit"), (9_000_000, 45_000_000)),
    "Phụ kiện": (("Kite", "Volta", "Linko"), (90_000, 1_500_000)),
    "Điện gia dụng": (("HomeOne", "Sunny", "Kaze"), (350_000, 12_000_000)),
    "Mỹ phẩm": (("Lotus", "Mira", "Senna"), (80_000, 1_200_000)),
    "Thực phẩm": (("Đồng Xanh", "Bếp Việt", "Mùa Vàng"), (15_000, 450_000)),
    "Đồ uống": (("Suối Mát", "Trà Xanh 9", "Cà Phê Đất"), (8_000, 300_000)),
    "Mẹ & Bé": (("BéYêu", "Mầm", "Tí Hon"), (60_000, 2_500_000)),
}
UOM_VARIANTS = {"cái": ["Cái", "cai", "pcs", "EA"], "hộp": ["Hộp", "hop", "box"], "chai": ["Chai", "chai ", "btl"]}

STORE_TYPES = ("store", "warehouse")
POSITIONS = ("Thu ngân", "Bán hàng", "Kho", "Quản lý cửa hàng", "Giao hàng", "Chăm sóc khách hàng")
TIERS = ("Bronze", "Silver", "Gold", "Diamond")
PAYMENT_METHODS = {"CASH": ["cash", "Tiền mặt", "TM"], "CARD": ["card", "Thẻ", "VISA"], "MOMO": ["momo", "Momo"]}
CARRIERS = {"GHN": ["ghn", "Giao Hàng Nhanh"], "GHTK": ["ghtk", "Giao Hàng Tiết Kiệm"], "VTP": ["Viettel Post", "vtp"]}
AD_CHANNELS = {
    "facebook": ["Facebook Ads", "FB", "facebook "],
    "google": ["Google Ads", "GG", "google"],
    "tiktok": ["TikTok"],
}
TICKET_CATEGORIES = ("giao hàng chậm", "đổi trả", "sai hàng", "thanh toán", "bảo hành", "hỏi thông tin")
RETURN_REASONS = ("Lỗi sản phẩm", "lỗi sp", "Không đúng mô tả", "Đổi ý", "doi y", "Giao sai hàng", "")
