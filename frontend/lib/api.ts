// Gọi API backend. Địa chỉ lấy từ NEXT_PUBLIC_API_URL; người dùng/vai trò gửi qua header X-User / X-Role.

import type { CurrentUser } from "./types";

// Không đặt NEXT_PUBLIC_API_URL: API cùng máy với trang web, cổng 8000 (mở bằng 127.0.0.1 hay IP mạng đều đúng).
function defaultApiUrl(): string {
  if (typeof window === "undefined") return "http://localhost:8000";
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || defaultApiUrl()).replace(/\/$/, "");
export const API_PREFIX = `${API_URL}/api/v1`;

const USER_KEY = "p113.user";
export const DEFAULT_USER: CurrentUser = { name: "de", role: "de" };

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function loadUser(): CurrentUser {
  try {
    const saved = JSON.parse(localStorage.getItem(USER_KEY) ?? "null") as CurrentUser | null;
    return saved?.name ? saved : DEFAULT_USER;
  } catch {
    return DEFAULT_USER;
  }
}

export function saveUser(user: CurrentUser): void {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // trình duyệt chặn lưu trữ: vẫn dùng được trong phiên này
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // phản hồi không phải JSON
  }
  return `Máy chủ trả lỗi ${response.status}. Vui lòng thử lại.`;
}

async function rawRequest(path: string, init?: RequestInit): Promise<string> {
  const user = loadUser();
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", "X-User": user.name, "X-Role": user.role },
    });
  } catch {
    throw new ApiError(`Không kết nối được máy chủ API (${API_URL}). Hãy kiểm tra backend đang chạy.`, 0);
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  return response.text();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return JSON.parse(await rawRequest(path, init)) as T;
}

/** GET trả nguyên văn JSON (để bỏ qua cập nhật khi dữ liệu không đổi — tránh vẽ lại cả trang mỗi lần hỏi). */
export function apiGetText(path: string): Promise<string> {
  return rawRequest(path);
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Có lỗi không xác định.";
}

export function downloadUrl(runId: string): string {
  return `${API_PREFIX}/runs/${runId}/download`;
}
