from alembic import context
from sqlalchemy.engine import make_url

from backend.config import database_url
from backend.database import make_engine
from backend.models import Base

url = database_url()

if context.is_offline_mode():
    context.configure(url=make_url(url), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
