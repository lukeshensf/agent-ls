from __future__ import annotations

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent_ls.config.settings import CONFIG_DIR

CHECKPOINT_DB = CONFIG_DIR / "checkpoints.db"


async def get_checkpointer() -> AsyncSqliteSaver:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_DB))
