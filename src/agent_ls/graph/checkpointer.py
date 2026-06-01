from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent_ls.config.settings import CONFIG_DIR

CHECKPOINT_DB = CONFIG_DIR / "checkpoints.db"


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[AsyncSqliteSaver]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as saver:
        yield saver
