# Đăng nhập và triển khai Vercel + Render

Tài liệu này mô tả phần auth PostgreSQL được bổ sung cho backend deploy hiện có. Backend không tự chạy migration lúc khởi động.

## Phạm vi lưu trữ

PostgreSQL chỉ lưu `users`, `sessions`, `audit_log` và `alembic_version`. SQLite của Run Store và LangGraph checkpoints, Error Book, workspaces, artifacts, file nguồn và DuckDB sandbox tiếp tục dùng các cấu hình hiện có (`STORE_PATH`, `CHECKPOINT_PATH`, `DATA_DIR`, `SOURCES_DIR`, `WORKSPACES_DIR`). Không có bước chuyển dữ liệu.

Render dùng filesystem tạm trừ khi dịch vụ được gắn persistent disk. Nếu các đường dẫn SQLite/workspace hiện tại nằm trên filesystem tạm, lịch sử run và checkpoint có thể mất sau khi dịch vụ khởi động lại hoặc được triển khai lại. Cần gắn disk vào đúng đường dẫn lưu trữ hiện có để giữ chúng; việc gắn/chuyển dữ liệu không được thực hiện tự động trong bản merge này. SQLite cũng yêu cầu backend chạy một instance duy nhất.

## PostgreSQL và quyền

Tạo một database auth riêng, sau đó cấp hai tài khoản PostgreSQL không phải superuser. Ví dụ dưới đây dùng `psql` kết nối bằng tài khoản DBA; thay tên database nếu cần:

```sql
CREATE DATABASE p113_auth;
CREATE ROLE p113_migrator LOGIN;
CREATE ROLE p113_app LOGIN;
GRANT CONNECT ON DATABASE p113_auth TO p113_migrator, p113_app;
```

Kết nối `psql` tới database `p113_auth` bằng tài khoản DBA, rồi cấp quyền schema:

```sql
GRANT USAGE, CREATE ON SCHEMA public TO p113_migrator;
GRANT USAGE ON SCHEMA public TO p113_app;
```

Đặt mật khẩu cho mỗi role riêng trong `psql` để mật khẩu không nằm trong câu lệnh đã lưu:

```text
\\password p113_migrator
\\password p113_app
```

- Tài khoản migration: sở hữu các bảng auth mới và có quyền tạo bảng/index trong schema đích.
- Tài khoản ứng dụng: `SELECT`, `INSERT`, `UPDATE` trên `users` và `sessions`; chỉ `SELECT`, `INSERT` trên `audit_log`; quyền `USAGE`/`SELECT` trên sequence cần dùng.

Tạo role ứng dụng trước khi migration chạy. Migration `0001_auth_tables` cấp quyền trên ba bảng auth nếu role trong `DB_APP_ROLE` đã tồn tại. Tài khoản ứng dụng không cần quyền DDL. Migration chỉ cấp quyền sequence cho ba sequence auth, không cấp quyền cho sequence khác trong schema. Không chạy migration bằng superuser và không dùng `DATABASE_URL` của ứng dụng làm tài khoản migration.

Trong môi trường production, chuỗi PostgreSQL cần SSL (`sslmode=require` hoặc chế độ xác minh TLS mạnh hơn) và driver `psycopg`, ví dụ dạng `postgresql+psycopg://...`. Không ghi chuỗi kết nối vào Git, log, tài liệu triển khai hay lệnh có thể lưu vào shell history.

## Biến môi trường

### Backend / Render runtime

| Biến | Cách đặt |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Chuỗi kết nối PostgreSQL của tài khoản ứng dụng, bật SSL |
| `SESSION_SECRET` | Giá trị ngẫu nhiên dài ít nhất 32 ký tự; sinh bằng password manager hoặc `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SESSION_TTL_MINUTES` | Thời hạn phiên, mặc định `480` |
| `SESSION_COOKIE_SECURE` | `true` trên HTTPS production |
| `SESSION_COOKIE_SAMESITE` | `lax` khi dùng proxy Vercel cùng miền |
| `CORS_ORIGINS` | Origin đầy đủ của Vercel, không có dấu `/` cuối; có thể liệt kê nhiều origin bằng dấu phẩy |
| `DB_APP_ROLE` | Tên role ứng dụng để migration cấp quyền, mặc định `p113_app` |
| `LOGIN_MAX_FAILURES` / `LOGIN_LOCK_MINUTES` | Ngưỡng khóa đăng nhập, mặc định `5` lần trong `15` phút |

Giữ nguyên toàn bộ biến LLM, Agent, sandbox và storage hiện có. `MIGRATION_DATABASE_URL` chỉ dành cho migration; không cần đưa vào tiến trình web thường trực của Render. Nếu migration được chạy trong môi trường one-off có kiểm soát, chỉ cấp biến này cho phiên đó.

### Frontend / Vercel

Đặt cả hai biến **trước khi build**:

| Biến | Giá trị |
|---|---|
| `BACKEND_URL` | Origin của backend Render, ví dụ `https://<service>.onrender.com` (không thêm `/api/v1`) |
| `NEXT_PUBLIC_API_URL` | `/` để trình duyệt chỉ gọi origin Vercel |

Không đưa `DATABASE_URL`, `SESSION_SECRET`, khóa LLM hay secret backend nào lên Vercel. External rewrite giữ nguyên đường dẫn `/api/v1/*` và chuyển tiếp tới Render; cookie phiên được đặt trên origin Vercel nên không cần third-party cookie. Backend vẫn cần Vercel trong `CORS_ORIGINS` vì CSRF kiểm tra `Origin` được proxy chuyển tiếp.

## Migration và Admin đầu tiên

Trước migration trên bất kỳ môi trường có dữ liệu, tạo và xác minh backup. Migration trong repository chỉ tạo ba bảng auth mới; không có migration schema snapshot và không có bước tự động lúc boot. Migration cố ý không hỗ trợ downgrade xóa bảng.

Sau khi chọn database staging riêng và được phép chạy migration ở đó, cài backend dependencies rồi chạy từ thư mục `backend/`:

```powershell
# Inject MIGRATION_DATABASE_URL from a secret manager or protected one-off job environment.
alembic upgrade head
alembic current
```

Không chạy các lệnh trên với URL production trước khi có backup và chấp thuận rõ ràng. `MIGRATION_DATABASE_URL` không được ghi vào shell history trong quy trình production; ưu tiên secret injection/one-off job. Không truyền mật khẩu bằng cờ CLI.

Tạo Admin đầu tiên sau khi migration thành công:

```powershell
python -m src.cli users create --username quantri --name "Quản trị" --role admin
```

CLI hỏi mật khẩu hai lần bằng input ẩn. Không có mật khẩu mặc định; không thêm mật khẩu vào command, repo hoặc log. Tài khoản Admin có thể tạo Engineer/Reviewer/Admin, khóa tài khoản, mở khóa và đặt lại mật khẩu. Khóa, đổi role hoặc đặt lại mật khẩu sẽ thu hồi các phiên hiện tại của tài khoản đó.

## Kiểm tra staging

1. Tạo database PostgreSQL staging mới và hai role theo nguyên tắc trên.
2. Chạy migration bằng role migration; xác minh ba bảng auth và `alembic_version`.
3. Tạo Admin đầu tiên bằng CLI, rồi đăng nhập qua URL Vercel staging.
4. Kiểm tra `GET /health`: `database` báo Run Store SQLite; `auth_database` báo PostgreSQL và migration auth. Endpoint chỉ trả trạng thái, không trả URL hay thông tin kết nối.
5. Kiểm tra đăng nhập, reload giữ phiên, logout thu hồi phiên, 401/403, Admin CRUD/audit và review ở cả hai giá trị `REQUIRE_SEPARATE_REVIEWER`.
6. Tạo Run mock ở staging để kiểm tra planner, clarification, duyệt kế hoạch, sinh code/test, review, resume/checkpoint và download. Kiểm tra LLM thật riêng khi đã có khóa test được phép dùng.
7. Xác nhận Render có persistent disk nếu cần bảo toàn Run Store, checkpoint và workspace qua restart.

## Rollback

Quay lại commit ứng dụng trước merge và build/deploy lại frontend/backend qua quy trình staging/production đã duyệt. Bản code cũ không đọc các bảng auth mới; giữ nguyên các bảng và dữ liệu PostgreSQL để lần triển khai sau có thể dùng lại. Không chạy downgrade, `DROP`, `TRUNCATE`, reset database hoặc xóa SQLite/checkpoint/workspace trong rollback. Nếu người dùng đã tạo dữ liệu tài khoản trong thời gian chạy bản mới, giữ database auth lại và xử lý tương thích trước lần bật auth kế tiếp.

## Giới hạn proxy và file tải

Run được tạo bất đồng bộ (API trả `202`) và UI đọc tiến trình bằng các request polling ngắn; request LLM dài không giữ kết nối proxy đang mở. Tải ZIP vẫn đi qua `/api/v1/runs/{id}/download`; external rewrites trên Vercel hoạt động như reverse proxy. Nếu đường dẫn tải được xử lý qua Vercel Function, tài liệu Vercel hiện nêu giới hạn body request/response 4.5 MB và thời lượng tối đa thay đổi theo gói/cấu hình. Vì giới hạn này không nhất thiết áp dụng giống nhau cho mọi external rewrite, đo dung lượng artifact và thử tải lớn trên đúng gói Vercel/Render staging trước khi dùng. Nếu ZIP vượt giới hạn thực tế, cần chuyển sang URL tải trực tiếp có kiểm soát hoặc object storage trong một thay đổi riêng. Tham khảo [Vercel Rewrites](https://vercel.com/docs/routing/rewrites) và [Vercel Function limits](https://vercel.com/docs/functions/limitations).
