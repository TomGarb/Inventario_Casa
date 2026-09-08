"""add_theme_and_dashboard_widgets

Revision ID: a3c891f7d24b
Revises: e5af5afc29b7
Create Date: 2026-09-08 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a3c891f7d24b'
down_revision = 'e5af5afc29b7'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tema_ui', sa.String(length=50), nullable=True, server_default='tema-neomorfico'))
        batch_op.add_column(sa.Column('widgets_dashboard', sa.Text(), nullable=True, server_default='["inventario","compras","finanzas","tareas","logistica","menus","metricas","mascotas"]'))

def downgrade():
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_column('widgets_dashboard')
        batch_op.drop_column('tema_ui')
