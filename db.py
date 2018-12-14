from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from settings import DB_LINK
from models import *

engine = create_engine(DB_LINK)
Model.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
