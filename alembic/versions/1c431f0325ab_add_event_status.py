"""add_event_status

Revision ID: 1c431f0325ab
Revises: 
Create Date: 2025-05-01 21:46:04.732807

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c431f0325ab'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('department_program')
    op.drop_constraint('event_department_association_department_id_fkey', 'event_department_association', type_='foreignkey')
    op.drop_constraint('event_department_association_event_id_fkey', 'event_department_association', type_='foreignkey')
    op.create_foreign_key(None, 'event_department_association', 'departments', ['department_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'event_department_association', 'events', ['event_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('event_program_association_program_id_fkey', 'event_program_association', type_='foreignkey')
    op.drop_constraint('event_program_association_event_id_fkey', 'event_program_association', type_='foreignkey')
    op.create_foreign_key(None, 'event_program_association', 'events', ['event_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'event_program_association', 'programs', ['program_id'], ['id'], ondelete='CASCADE')
    op.add_column('events', sa.Column('status', sa.Enum('UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED', name='eventstatus'), nullable=True))
    op.execute("UPDATE events SET status = 'UPCOMING'")
    op.alter_column('events', 'status', nullable=False)
    op.drop_constraint('events_program_id_fkey', 'events', type_='foreignkey')
    op.drop_constraint('events_department_id_fkey', 'events', type_='foreignkey')
    op.drop_column('events', 'department_id')
    op.drop_column('events', 'program_id')
    op.drop_constraint('program_department_association_department_id_fkey', 'program_department_association', type_='foreignkey')
    op.drop_constraint('program_department_association_program_id_fkey', 'program_department_association', type_='foreignkey')
    op.create_foreign_key(None, 'program_department_association', 'programs', ['program_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'program_department_association', 'departments', ['department_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint(None, 'programs', ['name'])
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'programs', type_='unique')
    op.drop_constraint(None, 'program_department_association', type_='foreignkey')
    op.drop_constraint(None, 'program_department_association', type_='foreignkey')
    op.create_foreign_key('program_department_association_program_id_fkey', 'program_department_association', 'programs', ['program_id'], ['id'])
    op.create_foreign_key('program_department_association_department_id_fkey', 'program_department_association', 'departments', ['department_id'], ['id'])
    op.add_column('events', sa.Column('program_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('events', sa.Column('department_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key('events_department_id_fkey', 'events', 'departments', ['department_id'], ['id'])
    op.create_foreign_key('events_program_id_fkey', 'events', 'programs', ['program_id'], ['id'])
    op.drop_column('events', 'status')
    op.execute("DROP TYPE eventstatus") 
    op.drop_constraint(None, 'event_program_association', type_='foreignkey')
    op.drop_constraint(None, 'event_program_association', type_='foreignkey')
    op.create_foreign_key('event_program_association_event_id_fkey', 'event_program_association', 'events', ['event_id'], ['id'])
    op.create_foreign_key('event_program_association_program_id_fkey', 'event_program_association', 'programs', ['program_id'], ['id'])
    op.drop_constraint(None, 'event_department_association', type_='foreignkey')
    op.drop_constraint(None, 'event_department_association', type_='foreignkey')
    op.create_foreign_key('event_department_association_event_id_fkey', 'event_department_association', 'events', ['event_id'], ['id'])
    op.create_foreign_key('event_department_association_department_id_fkey', 'event_department_association', 'departments', ['department_id'], ['id'])
    op.create_table('department_program',
    sa.Column('department_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('program_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name='department_program_department_id_fkey'),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], name='department_program_program_id_fkey'),
    sa.PrimaryKeyConstraint('department_id', 'program_id', name='department_program_pkey')
    )
    # ### end Alembic commands ###
