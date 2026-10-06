"""Hồi quy: API đọc catalog song song với luồng chạy pipeline không được làm hỏng bước V2 (kết nối DuckDB lệch cấu hình)."""

import duckdb

from src.agents.nodes.sandbox_run import mart_sample
from src.agents.tools.duckdb_tools import connect_read, describe_query, read_catalog


def test_mart_sample_while_catalog_reader_is_open(tmp_path):
    db = tmp_path / "sandbox.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE TABLE fct_x AS SELECT 1 AS id, 'a' AS name")
    with connect_read(db):  # catalog đang mở sandbox
        rows, sample = mart_sample(db, "fct_x")
        assert rows == 1 and sample[0]["id"] == "1"
        assert "id" in describe_query(db, "SELECT * FROM main.fct_x")
        assert "main" in read_catalog(db)
