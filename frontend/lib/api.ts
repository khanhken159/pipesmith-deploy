// Gọi API backend. Địa chỉ lấy từ NEXT_PUBLIC_API_URL. Người dùng xác định bằng cookie phiên HttpOnly do backend đặt
// khi đăng nhập (trang web không đọc được cookie này); mọi lời gọi gửi kèm cookie (credentials: "include").

// Không đặt NEXT_PUBLIC_API_URL: API cùng máy với trang web, cổng 8000 (mở bằng 127.0.0.1 hay IP mạng đều đúng).
function defaultApiUrl(): string {
  if (typeof window === "undefined") return "http://localhost:8000";
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || defaultApiUrl())
  .replace(/\/+$/, "")
  .replace(/\/api\/v1$/, "");
export const API_PREFIX = `${API_URL}/api/v1`;
/** Phát ra khi API trả 401 (chưa đăng nhập, hết phiên, bị khóa): AppContext đưa về trang đăng nhập. */
export const UNAUTHORIZED_EVENT = "p113:unauthorized";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
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
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    headers.set("X-Requested-With", "p113-web");
    response = await fetch(`${API_PREFIX}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      // X-Requested-With: backend chặn thao tác ghi thiếu header này (chống CSRF)
      headers,
    });
  } catch {
    throw new ApiError(
      `Không kết nối được máy chủ API (${API_URL || "cùng miền ứng dụng"}). Hãy kiểm tra backend đang chạy.`,
      0,
    );
  }
  if (response.status === 401 && !path.startsWith("/auth/login") && typeof window !== "undefined") {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  return response.text();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const text = await rawRequest(path, init);
  return (text ? JSON.parse(text) : null) as T;
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

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Có lỗi không xác định.";
}

export function downloadUrl(runId: string): string {
  return `${API_PREFIX}/runs/${runId}/download`;
}
