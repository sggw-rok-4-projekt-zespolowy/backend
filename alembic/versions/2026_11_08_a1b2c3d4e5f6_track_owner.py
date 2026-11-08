"""track owner

Revision ID: a1b2c3d4e5f6
Revises: 4f7ff38c7aaa
Create Date: 2026-11-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4f7ff38c7aaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The initial migration created an unnamed UNIQUE(deezer_track_id) constraint.
# PostgreSQL names it automatically; on SQLite the naming convention below
# gives the reflected constraint a name so batch mode can drop it.
NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _old_unique_name() -> str:
    if op.get_bind().dialect.name == "postgresql":
        return "track_deezer_track_id_key"
    return "uq_track_deezer_track_id"


def upgrade() -> None:
    with op.batch_alter_table("track", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(_old_unique_name(), type_="unique")
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_track_owner_id", ["owner_id"])
        batch_op.create_foreign_key("fk_track_owner_id_user", "user", ["owner_id"], ["id"])
        batch_op.create_unique_constraint(
            "uq_track_deezer_track_id_owner_id", ["deezer_track_id", "owner_id"]
        )


def downgrade() -> None:
    op.execute("DELETE FROM track WHERE owner_id IS NOT NULL")
    with op.batch_alter_table("track", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("uq_track_deezer_track_id_owner_id", type_="unique")
        batch_op.drop_constraint("fk_track_owner_id_user", type_="foreignkey")
        batch_op.drop_index("ix_track_owner_id")
        batch_op.drop_column("owner_id")
        batch_op.create_unique_constraint(_old_unique_name(), ["deezer_track_id"])
