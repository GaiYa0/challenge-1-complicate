"""
数据脱敏：手机号、银行卡号等；可在序列化前对 dict/str 处理。
"""

from __future__ import annotations

import re
from typing import Any


def mask_phone(value: str | None) -> str | None:
    """
    手机号 → 138****1234（保留前 3 与后 4 位，中间 4 位掩码）。
    非 11 位数字则原样返回或弱掩码。
    """
    if not value:
        return value
    s = re.sub(r"\D", "", str(value))
    if len(s) == 11:
        return f"{s[:3]}****{s[-4:]}"
    if len(s) >= 7:
        return f"{s[:3]}****{s[-4:]}"
    return "****"


def mask_bank_card(value: str | None) -> str | None:
    """
    银行卡 → ****1234（仅保留后 4 位）。
    """
    if not value:
        return value
    s = re.sub(r"\D", "", str(value))
    if len(s) >= 4:
        return f"****{s[-4:]}"
    return "****"


def mask_id_card(value: str | None) -> str | None:
    """身份证号：保留前 6 与后 4。"""
    if not value:
        return value
    s = re.sub(r"\D", "", str(value))
    if len(s) >= 10:
        return f"{s[:6]}********{s[-4:]}"
    return "****"


def mask_dict_values(
    data: dict[str, Any],
    *,
    phone_keys: frozenset[str] | None = None,
    bank_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    """浅层脱敏：匹配常见键名。"""
    pk = phone_keys or frozenset(
        {"phone", "mobile", "msisdn", "tel", "caller", "callee", "手机号", "电话"}
    )
    bk = bank_keys or frozenset({"bank_card", "card_no", "bankAccount", "银行卡", "卡号"})
    out: dict[str, Any] = {}
    for k, v in data.items():
        lk = str(k).lower()
        if lk in pk or any(x in lk for x in ("phone", "mobile", "caller", "callee")):
            out[k] = mask_phone(str(v)) if v is not None else v
        elif lk in bk or "card" in lk and "name" not in lk:
            out[k] = mask_bank_card(str(v)) if v is not None else v
        else:
            out[k] = v
    return out
