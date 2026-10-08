// Kiểm tương phản chữ/nền ≥ 4.5:1 (WCAG AA) cho mọi cặp màu giao diện dùng thật, cả sáng lẫn tối.
// Đọc styles/tokens.css (mỗi biến dạng light-dark(<sáng>, <tối>)). Cặp nào trượt → thoát mã 1: chỉnh màu, không bỏ qua.
//   npm run check:contrast

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const MIN_RATIO = 4.5;
const TOKENS = join(dirname(fileURLToPath(import.meta.url)), "..", "styles", "tokens.css");

// [chữ, nền, chỗ dùng] — thêm cặp mới khi globals.css dùng một tổ hợp mới.
const PAIRS = [
  ["text", "bg", "chữ thường trên nền trang"],
  ["text", "surface", "chữ trong thẻ"],
  ["text", "surface-2", "chữ trong ô thống kê, tiêu đề bảng"],
  ["muted", "bg", "chữ phụ trên nền trang"],
  ["muted", "surface", "chữ phụ trong thẻ"],
  ["muted", "surface-2", "nhãn ô thống kê, tiêu đề cột"],
  ["primary", "surface", "liên kết, tab đang chọn"],
  ["primary", "bg", "liên kết trên nền trang"],
  ["primary", "primary-soft", "mục điều hướng đang chọn, nhãn thông tin"],
  ["primary-ink", "primary", "nút chính"],
  ["ok", "ok-soft", "nhãn đạt"],
  ["ok", "surface", "dấu đạt trên thẻ"],
  ["ok-ink", "ok", "nút duyệt"],
  ["warn", "warn-soft", "nhãn chờ người, cảnh báo"],
  ["warn", "surface", "chữ cảnh báo trên thẻ"],
  ["fail", "fail-soft", "nhãn lỗi, hộp lỗi"],
  ["fail", "surface", "nút từ chối (viền), chữ lỗi"],
  ["text", "frame", "chữ trên khung kính (tiêu đề trang, thanh điều hướng)"],
  ["muted", "frame", "chữ phụ trên khung kính, chân trang"],
  ["primary", "frame", "tab điều hướng đang chọn"],
  ["primary-ink", "accent", "chữ trên logo gradient"],
  ["console-text", "console-bg", "dòng log trong console"],
  ["console-muted", "console-bg", "giờ, nhãn phụ trong console"],
  ["console-ok", "console-bg", "nhãn OK trong console"],
  ["console-fail", "console-bg", "nhãn LỖI trong console"],
  ["console-info", "console-bg", "nhãn bước trong console"],
  ["console-live", "console-bg", "dòng 'đang làm' (mô tả, không phải log đo)"],
  ["text", "glass-solid", "chữ trong thẻ kính"],
  ["muted", "glass-solid", "chữ phụ trong thẻ kính"],
  ["primary", "glass-solid", "liên kết, số lớn trong thẻ kính"],
  ["hero-ink", "sky-mid", "tiêu đề lớn trên bầu trời"],
  ["hero-ink", "sky-top", "tiêu đề lớn ở mép trên bầu trời"],
  ["hero-ink", "horizon", "chữ hero gần chân trời"],
  ["rail-ink", "rail", "biểu tượng thanh điều hướng dọc đang chọn"],
];

function parseTokens(css) {
  const tokens = {};
  for (const match of css.matchAll(/--([a-z0-9-]+):\s*light-dark\(\s*(#[0-9a-f]{6})\s*,\s*(#[0-9a-f]{6})\s*\)/gi)) {
    tokens[match[1]] = { light: match[2], dark: match[3] };
  }
  return tokens;
}

function luminance(hex) {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const tokens = parseTokens(readFileSync(TOKENS, "utf8"));
let failed = 0;
for (const mode of ["light", "dark"]) {
  console.log(`\n${mode === "light" ? "Sáng" : "Tối"}`);
  for (const [fg, bg, usage] of PAIRS) {
    if (!tokens[fg] || !tokens[bg]) {
      console.log(`  ✗ thiếu biến --${!tokens[fg] ? fg : bg} trong tokens.css`);
      failed += 1;
      continue;
    }
    const value = ratio(tokens[fg][mode], tokens[bg][mode]);
    const ok = value >= MIN_RATIO;
    if (!ok) failed += 1;
    console.log(`  ${ok ? "✓" : "✗"} ${value.toFixed(2).padStart(5)}:1  --${fg} / --${bg}  (${usage})`);
  }
}
if (failed) {
  console.error(`\n${failed} cặp dưới ${MIN_RATIO}:1 — chỉnh màu trong styles/tokens.css.`);
  process.exit(1);
}
console.log(`\nMọi cặp đạt ≥ ${MIN_RATIO}:1.`);
