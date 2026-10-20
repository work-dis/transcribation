"""Initial schema revision marker."""
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    from alembic import op
    from conversation_core.db import Base
    Base.metadata.create_all(op.get_bind())
def downgrade():
    from alembic import op
    from conversation_core.db import Base
    Base.metadata.drop_all(op.get_bind())
