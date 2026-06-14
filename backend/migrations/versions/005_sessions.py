"""add local copilot session metadata

Revision ID: 005_sessions
Revises: 004_chat_sessions
Create Date: 2026-06-14 10:45:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_sessions"
down_revision: Union[str, None] = "004_chat_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "copilot_sessions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("node_map_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("current_leaf_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_sessions_updated_at", "copilot_sessions", ["updated_at"])
    op.create_index("ix_copilot_sessions_deleted_at", "copilot_sessions", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_copilot_sessions_deleted_at", table_name="copilot_sessions")
    op.drop_index("ix_copilot_sessions_updated_at", table_name="copilot_sessions")
    op.drop_table("copilot_sessions")
