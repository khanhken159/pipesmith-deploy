"""E2 Dữ liệu thử (code tất định, seed cố định): sinh các bộ small / large / dirty / empty / few / dupkeys.

Mỗi bộ là một file DuckDB riêng có cùng schema `raw` với sandbox, dùng cho đo tốc độ (large) và đối chiếu (V3).
"""

import math
import re
from collections.abc import Callable
from pathlib import Path

import duckdb
from pydantic import BaseModel

from src.agents.nodes.common import sandbox_db
from src.agents.state import PipelineState
from src.agents.tools.duckdb_tools import RAW_SCHEMA, quote_path
from src.config import get_settings

DATASET_NAMES = ("small", "large", "dirty", "empty", "few", "dupkeys")
NUMERIC_TYPES = ("BIGINT", "INTEGER", "HUGEINT", "SMALLINT")
LINK_NAME_RE = re.compile(r"^(id|sku|.*_(id|code|ref))$", re.I)


class TableRecipe(BaseModel):
    """Thông tin để sinh dữ liệu cho một bảng."""

    table: str
    rows: int
    key: str = ""
    key_numeric: bool = False
    money_columns: list[str] = []
    link_columns: dict[str, bool] = {}  # cột dạng khóa (nối giữa các bảng) → có phải kiểu số không


def _src(recipe: TableRecipe) -> str:
    return f'src.{RAW_SCHEMA}."{recipe.table}"'


def _order(recipe: TableRecipe) -> str:
    return f'"{recipe.key}"' if recipe.key else "ALL"


def _small(recipe: TableRecipe) -> str:
    settings = get_settings()
    return f"SELECT * FROM {_src(recipe)} USING SAMPLE reservoir({settings.mock_small_rows} ROWS) REPEATABLE ({settings.seed})"


def _copy_value(column: str, numeric: bool) -> str:
    """Giá trị cột khóa ở bản sao thứ g (g = 0 giữ nguyên) — mọi bảng dùng cùng quy tắc nên nối vẫn khớp trong bản sao."""
    col = f'"{column}"'
    shifted = f"{col} + g * 100000000" if numeric else f"{col} || '-' || g"
    return f"CASE WHEN g = 0 THEN {col} ELSE {shifted} END AS {col}"


def _large(recipe: TableRecipe) -> str:
    """Nhân bản tới ~mock_large_rows dòng. Mọi cột khóa (cả khóa ngoại như sku, store_code) đổi theo bản sao, nên
    bảng danh mục nhân bản không làm phép nối bùng nổ (mỗi dòng bán chỉ khớp sản phẩm cùng bản sao)."""
    copies = max(1, math.ceil(get_settings().mock_large_rows / max(recipe.rows, 1)))
    links = dict(recipe.link_columns)
    if recipe.key:
        links.setdefault(recipe.key, recipe.key_numeric)
    if not links:
        return f"SELECT t.* FROM {_src(recipe)} t, range({copies}) r(g)"
    replaced = ", ".join(_copy_value(column, numeric) for column, numeric in links.items())
    return f"SELECT t.* REPLACE ({replaced}) FROM {_src(recipe)} t, range({copies}) r(g)"


def _numbered(recipe: TableRecipe) -> str:
    order = f'"{recipe.key}"' if recipe.key else "1"
    return f"WITH s AS (SELECT *, row_number() OVER (ORDER BY {order}) AS __rn FROM ({_small(recipe)}))"


def _dirty(recipe: TableRecipe) -> str:
    nulls = ", ".join(f'CASE WHEN __rn % 7 = 0 THEN NULL ELSE "{c}" END AS "{c}"' for c in recipe.money_columns)
    replace = f" REPLACE ({nulls})" if nulls else ""
    return (
        f"{_numbered(recipe)} SELECT * EXCLUDE (__rn){replace} FROM s "
        "UNION ALL SELECT * EXCLUDE (__rn) FROM s WHERE __rn <= 5"
    )


def _dupkeys(recipe: TableRecipe) -> str:
    if not recipe.key:
        return f"{_numbered(recipe)} SELECT * EXCLUDE (__rn) FROM s UNION ALL SELECT * EXCLUDE (__rn) FROM s WHERE __rn <= 5"
    key = f'"{recipe.key}"'
    return (
        f"{_numbered(recipe)} SELECT * EXCLUDE (__rn) FROM s UNION ALL "
        f"SELECT a.* EXCLUDE (__rn) REPLACE (b.{key} AS {key}) FROM s a JOIN s b ON b.__rn = a.__rn + 1 WHERE a.__rn <= 5"
    )


RECIPES: dict[str, Callable[[TableRecipe], str]] = {
    "small": _small,
    "large": _large,
    "dirty": _dirty,
    "empty": lambda r: f"SELECT * FROM {_src(r)} LIMIT 0",
    "few": lambda r: f"SELECT * FROM {_src(r)} ORDER BY {_order(r)} LIMIT 3",
    "dupkeys": _dupkeys,
}


class DatasetJob(BaseModel):
    """Sinh bộ dữ liệu `name` từ `source_db` vào file `target`."""

    name: str
    source_db: Path
    target: Path


def build_dataset(job: DatasetJob, recipes: list[TableRecipe]) -> None:
    """Tạo một bộ dữ liệu thử từ bảng raw của sandbox (một luồng để lấy mẫu lặp lại được)."""
    job.target.unlink(missing_ok=True)
    with duckdb.connect(str(job.target)) as con:
        con.execute("SET threads = 1")
        con.execute(f"ATTACH {quote_path(job.source_db)} AS src (READ_ONLY)")
        con.execute(f"CREATE SCHEMA {RAW_SCHEMA}")
        for recipe in recipes:
            con.execute(f'CREATE TABLE {RAW_SCHEMA}."{recipe.table}" AS {RECIPES[job.name](recipe)}')
        con.execute("DETACH src")


def recipes_from_profile(profile: dict) -> list[TableRecipe]:
    """Lấy khóa, cột tiền, số dòng của từng bảng từ hồ sơ dữ liệu."""
    recipes = []
    for table, info in profile.items():
        key = info.get("key_column", "")
        links = {c: col["type"] in NUMERIC_TYPES for c, col in info["columns"].items() if LINK_NAME_RE.match(c)}
        recipes.append(
            TableRecipe(
                table=table,
                rows=info["rows"],
                key=key,
                key_numeric=bool(key) and info["columns"][key]["type"] in NUMERIC_TYPES,
                money_columns=info.get("money_columns", []),
                link_columns=links,
            )
        )
    return recipes


def mock_data_node(state: PipelineState) -> dict:
    """Sinh đủ các bộ dữ liệu thử vào `<workspace>/datasets/`."""
    folder = Path(state["workspace"]) / "datasets"
    folder.mkdir(parents=True, exist_ok=True)
    recipes = recipes_from_profile(state.get("profile", {}))
    datasets = {}
    for name in DATASET_NAMES:
        datasets[name] = str(folder / f"{name}.duckdb")
        build_dataset(DatasetJob(name=name, source_db=sandbox_db(state), target=Path(datasets[name])), recipes)
    return {"datasets": datasets}
