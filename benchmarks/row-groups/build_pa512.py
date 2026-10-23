"""Rewrite collections-rg2048.parquet with 512-row row groups, which DuckDB cannot write. usage: uv run python build_pa512.py"""
import pyarrow.parquet as pq
pq.write_table(pq.read_table("collections-rg2048.parquet"), "collections-pa512.parquet", row_group_size=512, compression="zstd", write_statistics=True)
