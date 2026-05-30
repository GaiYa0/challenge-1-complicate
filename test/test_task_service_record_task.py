from __future__ import annotations

from dataclasses import dataclass
import sys
import types

import pytest
from sqlalchemy.exc import IntegrityError

# 部分本地测试环境未安装 pydantic-settings，补最小桩以便导入 task_service。
if "pydantic_settings" not in sys.modules:
    stub = types.ModuleType("pydantic_settings")

    class BaseSettings:  # type: ignore[too-many-ancestors]
        pass

    class SettingsConfigDict(dict):
        pass

    stub.BaseSettings = BaseSettings
    stub.SettingsConfigDict = SettingsConfigDict
    sys.modules["pydantic_settings"] = stub

from backend.core.exceptions import ServiceError
from backend.app.services import task_service


@dataclass
class _FakeExistingRow:
    user_id: int | None


class _FakeScalarResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeDB:
    def __init__(self, *, flush_exc: Exception | None = None, existing_row=None):
        self.flush_exc = flush_exc
        self.existing_row = existing_row
        self.rollback_called = 0
        self.execute_called = 0

    def add(self, _obj):
        return None

    def flush(self):
        if self.flush_exc is not None:
            raise self.flush_exc
        return None

    def rollback(self):
        self.rollback_called += 1

    def execute(self, _stmt):
        self.execute_called += 1
        return _FakeScalarResult(self.existing_row)


class _Diag:
    def __init__(self, constraint_name: str):
        self.constraint_name = constraint_name


class _Orig:
    def __init__(self, pgcode: str, constraint_name: str):
        self.pgcode = pgcode
        self.diag = _Diag(constraint_name)


def _mk_integrity_error(pgcode: str, constraint_name: str) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, _Orig(pgcode, constraint_name))


def test_record_task_idempotent_for_same_user_duplicate_task_id():
    db = _FakeDB(
        flush_exc=_mk_integrity_error("23505", "ix_celery_task_runs_celery_task_id"),
        existing_row=_FakeExistingRow(user_id=1),
    )

    task_service._record_task(db, task_id="t1", task_name="clean_data", user_id=1)

    assert db.rollback_called == 1
    assert db.execute_called == 1


def test_record_task_idempotent_for_same_user_duplicate_task_id_alt_constraint_name():
    db = _FakeDB(
        flush_exc=_mk_integrity_error("23505", "celery_task_runs_celery_task_id_key"),
        existing_row=_FakeExistingRow(user_id=1),
    )

    task_service._record_task(db, task_id="t1", task_name="clean_data", user_id=1)

    assert db.rollback_called == 1
    assert db.execute_called == 1


def test_record_task_rejects_duplicate_task_id_owned_by_other_user():
    db = _FakeDB(
        flush_exc=_mk_integrity_error("23505", "ix_celery_task_runs_celery_task_id"),
        existing_row=_FakeExistingRow(user_id=2),
    )

    with pytest.raises(ServiceError, match="failed to record task"):
        task_service._record_task(db, task_id="t1", task_name="clean_data", user_id=1)

    assert db.rollback_called == 1
    assert db.execute_called == 1


def test_record_task_rejects_non_unique_integrity_error():
    db = _FakeDB(
        flush_exc=_mk_integrity_error("23503", "fk_other_constraint"),
        existing_row=_FakeExistingRow(user_id=1),
    )

    with pytest.raises(ServiceError, match="failed to record task"):
        task_service._record_task(db, task_id="t1", task_name="clean_data", user_id=1)

    assert db.rollback_called == 1
    # 非唯一键冲突时，不应走“按 task_id 查重并放行”的分支。
    assert db.execute_called == 0
