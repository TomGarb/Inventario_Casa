"""add_dashboard_layouts_and_tv_tablet_widgets

Revision ID: b4d91e82f3a1
Revises: a3c891f7d24b
Create Date: 2026-09-08 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b4d91e82f3a1'
down_revision = 'a3c891f7d24b'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dashboard_layout', sa.String(length=50), nullable=True, server_default='layout-launchpad'))

    with op.batch_alter_table('casas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('widgets_tv', sa.Text(), nullable=True, server_default='["clima","stock","tareas","menus","deportes","logistica","finanzas"]'))
        batch_op.add_column(sa.Column('widgets_tablet', sa.Text(), nullable=True, server_default='["compras","tareas","menus","mascotas"]'))

def downgrade():
    with op.batch_alter_table('casas', schema=None) as batch_op:
        batch_op.drop_column('widgets_tablet')
        batch_op.drop_column('widgets_tv')

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_column('dashboard_layout')
