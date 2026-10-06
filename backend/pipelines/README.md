# pipelines/

- `template/` — dự án dbt mẫu (dbt-duckdb). Agent chép thư mục này cho mỗi lần chạy.
- `workspaces/<run_id>/` — sinh lúc chạy (git-ignored): code dbt + DAG do agent sinh, `sandbox.duckdb`, bộ dữ liệu thử `datasets/`.
