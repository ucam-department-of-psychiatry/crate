from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base


metadata = MetaData()
Base = declarative_base(metadata=metadata)
