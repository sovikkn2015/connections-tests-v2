"""Task 6 -- Checkpointer factory (memory backend; stub paths for postgres/dynamodb)."""

import pytest

from m8_pipeline_engine.checkpointer import (
    DynamoDbSaver,
    PostgresSaver,
    build_checkpointer,
)


class _Cfg:
    def __init__(self, backend):
        self.checkpointer_backend = backend
        self.checkpointer_dsn_vault_path = "secret/data/m8/test"


def test_build_checkpointer_memory():
    ckpt = build_checkpointer(_Cfg("memory"))
    from langgraph.checkpoint.memory import InMemorySaver
    assert isinstance(ckpt, InMemorySaver)


def test_build_checkpointer_unknown():
    with pytest.raises(ValueError, match="unknown_checkpointer_backend"):
        build_checkpointer(_Cfg("oracle"))


def test_dynamodb_stub_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Phase 3"):
        DynamoDbSaver()


def test_postgres_saver_class_exists():
    # The wrapper is importable even without the library installed
    assert PostgresSaver is not None
