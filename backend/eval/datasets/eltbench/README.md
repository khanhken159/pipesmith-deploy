# Tập con ELT-Bench-Verified (10 pipeline)

Dữ liệu dùng để chấm độ đúng toàn luồng của P-113 (`eval/benchmarks/eltbench/`).

- **Nguồn:** ELT-Bench-Verified — <https://github.com/czanoli/ELT-Bench> (nhánh `elt-bench-pr`),
  dựa trên ELT-Bench gốc (IBM Research, ETH Zürich, UIUC).
- **Giấy phép:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Thư mục này giữ nguyên giấy phép đó;
  ai dùng lại phải ghi nguồn và chia sẻ theo cùng giấy phép.
- **Đã thay đổi so với bản gốc:**
  - Chỉ lấy 10 task nhẹ nhất (danh sách ở `eval/benchmarks/eltbench/tasks.yaml`).
  - CSV từ postgres/mongodb/API/flat file được chuyển sang Parquet có kiểu, để giống dữ liệu Airbyte nạp vào kho.
  - Bỏ phần Airbyte, Terraform và cấu hình Snowflake.

Mỗi task có các phần sau:

| Phần | Nội dung |
|---|---|
| `sources/` | Bảng nguồn thô |
| `data_model.yaml` | Yêu cầu: bảng đích và mô tả cột |
| `ground_truth/` | Bảng kết quả đúng (`gt_verified`) |
| `evaluation/` | Câu kiểm tra gốc |
| `manifest.json` | Danh sách bảng nguồn và nguồn gốc của từng bảng |

Tạo lại thư mục này từ bản tải về (chỉ đọc thư mục tải về, không sửa nó):

```powershell
python eval/benchmarks/eltbench/import_eltbench.py --src "<thư mục chứa ELT-Bench-Verified và eltbench_raw>"
```
