import pandas as pd
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest


_MODULE_PATH = Path(__file__).resolve().parents[1] / "backend" / "data_platform" / "normalization_engine.py"
_SPEC = spec_from_file_location("normalization_engine", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
clean_and_standardize = _MOD.clean_and_standardize

from backend.app.services.file_service import (
    _frame_from_raw_with_header_detection,
    _normalize_table_df,
    read_tabular_bytes_to_dataframe,
)
from backend.core.exceptions import ServiceError


def test_fuzzy_header_mapping_and_standard_output():
    df = pd.DataFrame(
        {
            "付款人 ": ["张三", "李四"],
            "receiver": ["王五", "赵六"],
            "交易金额(元)": ["¥1,200.50", "3000"],
            "trade_time": ["2026-01-01 10:00:00", "2026/01/02 09:30"],
            " 交易地点 ": ["北京市朝阳区", "上海市浦东新区"],
        }
    )
    out = clean_and_standardize(df)
    clean_df = out["clean_df"]
    assert {"from_user", "to_user", "amount", "timestamp", "location"}.issubset(set(clean_df.columns))
    assert float(clean_df["amount"].iloc[0]) == 1200.5
    assert str(clean_df["from_user"].iloc[0]) == "张三"


def test_content_inference_without_standard_headers():
    df = pd.DataFrame(
        {
            "col_a": ["13800138000", "13900139000"],
            "col_b": ["110101199001011234", "110101199201011111"],
            "col_c": ["2026-05-01 08:00:00", "2026-05-02 09:00:00"],
            "col_d": ["1234.56", "88.99"],
            "col_e": ["北京市海淀区中关村大街1号", "上海市静安区南京西路1号"],
        }
    )
    out = clean_and_standardize(df)
    clean_df = out["clean_df"]
    assert "amount" in clean_df.columns
    assert "timestamp" in clean_df.columns
    assert "location" in clean_df.columns


def test_out_of_order_columns():
    df = pd.DataFrame(
        {
            "金额": [10, 20],
            "地点": ["A路", "B街"],
            "收款人": ["乙", "丁"],
            "付款人": ["甲", "丙"],
            "时间": ["2026-01-01", "2026-01-02"],
        }
    )
    out = clean_and_standardize(df)
    clean_df = out["clean_df"]
    assert list(clean_df["from_user"]) == ["甲", "丙"]
    assert list(clean_df["to_user"]) == ["乙", "丁"]


def test_header_detection_should_not_merge_first_data_row():
    df_raw = pd.DataFrame(
        [
            ["用户ID", "交易单号", "用户侧账号名称", "交易时间", "交易金额(分)"],
            ["tom123", "1", "张三", "2023-07-14 23:48:00", "1500"],
            ["tom123", "2", "张三", "2023-07-21 23:28:00", "3000"],
        ]
    )
    out = _frame_from_raw_with_header_detection(df_raw)
    assert out.columns.tolist() == ["用户ID", "交易单号", "用户侧账号名称", "交易时间", "交易金额(分)"]
    assert out.iloc[0]["用户ID"] == "tom123"


def test_header_detection_should_merge_real_two_level_header():
    df_raw = pd.DataFrame(
        [
            ["交易", "交易", "对手方"],
            ["时间", "金额", "名称"],
            ["2024-01-01 10:00:00", "1200", "李四"],
        ]
    )
    out = _frame_from_raw_with_header_detection(df_raw)
    assert out.columns.tolist() == ["交易_时间", "交易_金额", "对手方_名称"]
    assert out.iloc[0]["对手方_名称"] == "李四"


def test_header_detection_should_merge_grouped_top_header_without_keywords():
    df_raw = pd.DataFrame(
        [
            ["A组", "A组", "B组", "B组"],
            ["foo", "bar", "baz", "qux"],
            ["1", "2", "3", "4"],
        ]
    )
    out = _frame_from_raw_with_header_detection(df_raw)
    assert out.columns.tolist() == ["A组_foo", "A组_bar", "B组_baz", "B组_qux"]


def test_header_detection_should_not_merge_name_like_first_data_row():
    df_raw = pd.DataFrame(
        [
            ["付款方", "收款方", "用途"],
            ["张三", "李四", "转账"],
            ["王五", "赵六", "购物"],
        ]
    )
    out = _frame_from_raw_with_header_detection(df_raw)
    assert out.columns.tolist() == ["付款方", "收款方", "用途"]
    assert out.iloc[0]["付款方"] == "张三"


def test_header_detection_grouped_top_should_not_merge_chinese_name_data_row():
    df_raw = pd.DataFrame(
        [
            ["A组", "A组", "B组", "B组"],
            ["张三", "李四", "王五", "赵六"],
            ["记录1", "记录2", "记录3", "记录4"],
        ]
    )
    out = _frame_from_raw_with_header_detection(df_raw)
    assert out.columns.tolist() == ["A组", "A组_2", "B组", "B组_2"]
    assert out.iloc[0]["A组"] == "张三"


def test_header_detection_should_merge_abbreviation_second_header_row():
    df_raw = pd.DataFrame(
        [
            ["交易信息", "账户信息", "账户信息"],
            ["id", "amt", "no"],
            ["T001", "100.00", "A1001"],
        ]
    )
    out = _frame_from_raw_with_header_detection(df_raw)
    assert out.columns.tolist() == ["交易信息_id", "账户信息_amt", "账户信息_no"]


def test_invisible_control_chars_are_sanitized_from_columns():
    df = pd.DataFrame([["x", "y"]], columns=["备注\u200c\u200e\u202a\u202c", "交易\u2060时间"])
    out = _normalize_table_df(df)
    assert out.columns.tolist() == ["备注", "交易时间"]


def test_fake_xls_text_should_fallback_to_text_parser():
    raw = "用户ID,交易金额(分)\ntom123,1500\n".encode("utf-8")
    out = read_tabular_bytes_to_dataframe("TenpayTrades.xls", raw)
    assert out.shape[0] == 1
    assert "用户ID" in out.columns


def test_binary_xls_parse_failure_should_raise_service_error(monkeypatch: pytest.MonkeyPatch):
    def _raise(*args, **kwargs):
        raise ValueError("broken excel")

    monkeypatch.setattr("backend.app.services.file_service.pd.read_excel", _raise)
    with pytest.raises(ServiceError):
        read_tabular_bytes_to_dataframe("sample.xls", b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1abcd")
