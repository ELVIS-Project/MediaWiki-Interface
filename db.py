import sqlite3
from sqlalchemy import Column, Integer, String, Boolean, create_engine, ForeignKey, Float
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from settings import SQLITE_FILE

Base = declarative_base()
engine = create_engine('sqlite:////{}'.format(SQLITE_FILE))


class Composer(Base):
    __tablename__ = 'composers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)

    pieces = relationship("Piece", back_populates='composer')
    scores = relationship("Score", back_populates='composer')

    all_scraped = Column(Boolean, default=False)
    all_downloaded = Column(Boolean, default=False)
    failed_scrape = Column(Boolean, default=False)

    def __repr__(self):
        st = '<Composer(name="{}", url="{}")>'
        return st.format(self.name, self.url)


class Piece(Base):
    __tablename__ = 'pieces'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    url = Column(String, nullable=False, unique=True)

    composer_id = Column(Integer, ForeignKey('composers.id'))
    composer = relationship('Composer', back_populates='pieces')
    scores = relationship("Score", back_populates='piece')

    json_metadata = Column(String)
    html_dump = Column(String)

    scraped = Column(Boolean, default=False)
    all_downloaded = Column(Boolean, default=False)
    failed_scrape = Column(Boolean, default=False)

    def __repr__(self):
        st = '<Piece(name="{}", url="{}")>'
        return st.format(self.name, self.url)


class Score(Base):
    __tablename__ = 'scores'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    url = Column(String, nullable=False, unique=True)

    composer_id = Column(Integer, ForeignKey('composers.id'))
    piece_id = Column(Integer, ForeignKey('pieces.id'))

    piece = relationship('Piece', back_populates='scores')
    composer = relationship('Composer', back_populates='scores')

    downloaded = Column(Boolean, default=False)
    failed_scrape = Column(Boolean, default=False)
    file_path = Column(String)

    rating_count = Column(Integer)
    rating = Column(Float)
    file_format = Column(String)

    def __repr__(self):
        st = '<Score(name="{}", url="{}")>'
        return st.format(self.name, self.url)

Base.metadata.create_all(engine)
DB_SESSION = sessionmaker(bind=engine)


def migration1():
    """Add rating columns to scores, set bool defaults to false.

    This migration was applied after Composers were scraped but
    before pieces had begun to be scraped.
    """
    conn = sqlite3.connect(SQLITE_FILE)
    conn.execute("""ALTER TABLE scores ADD rating_count INT;""")
    conn.execute("""ALTER TABLE scores ADD rating FLOAT;""")
    conn.execute("""ALTER TABLE scores ADD file_format STRING;""")

    session = DB_SESSION()
    for piece in session.query(Piece).all():
        piece.scraped = False
        piece.all_downloaded = False
    session.commit()


def migration2():
    """Add a 'failed_scrape' column to all models.

    This migration was applied after I found I needed a way to avoid getting in a cycle
    of repeatedly trying to scrape things that were broken.
    """
    conn = sqlite3.connect(SQLITE_FILE)
    conn.execute("""ALTER TABLE scores ADD failed_scrape BOOLEAN DEFAULT FALSE;""")
    conn.execute("""ALTER TABLE pieces ADD failed_scrape BOOLEAN DEFAULT FALSE;""")
    conn.execute("""ALTER TABLE composers ADD failed_scrape BOOLEAN DEFAULT FALSE;""")

    session = DB_SESSION()
    for piece in session.query(Piece).all():
        piece.failed_scrape = False
    session.commit()
    for composer in session.query(Composer).all():
        composer.failed_scrape = False
    session.commit()
    for score in session.query(Score).all():
        score.failed_scrape = False
    session.commit()
