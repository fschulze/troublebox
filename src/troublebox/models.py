from lazy import lazy
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Unicode
from sqlalchemy import engine_from_config
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import configure_mappers
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
import zope.sqlalchemy


Base = declarative_base()


class Event(Base):
    __tablename__ = 'events'

    id = Column(Integer(), primary_key=True)
    event_id = Column(Unicode(), unique=True)
    project = Column(Integer(), index=True)
    _project = relationship(
        "Project",
        primaryjoin="Event.project == foreign(Project.id)",
        uselist=False)
    data = Column(JSON())

    @lazy
    def project_title(self):
        if self._project and self._project.title:
            return self._project.title
        return "(%s)" % self.project


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer(), primary_key=True)
    title = Column(Unicode(), nullable=True)


configure_mappers()


def get_engine(settings, prefix='sqlalchemy.'):
    return engine_from_config(settings, prefix)


def get_session_factory(engine):
    factory = sessionmaker()
    factory.configure(bind=engine)
    return factory


def get_tm_session(session_factory, transaction_manager):
    dbsession = session_factory()
    zope.sqlalchemy.register(
        dbsession, transaction_manager=transaction_manager)
    return dbsession


def includeme(config):
    settings = config.get_settings()
    settings['tm.manager_hook'] = 'pyramid_tm.explicit_manager'

    # use pyramid_tm to hook the transaction lifecycle to the request
    config.include('pyramid_tm')

    # use pyramid_retry to retry a request when transient exceptions occur
    config.include('pyramid_retry')

    session_factory = get_session_factory(get_engine(settings))
    config.registry['dbsession_factory'] = session_factory

    # make request.dbsession available for use in Pyramid
    config.add_request_method(
        # r.tm is the transaction manager used by pyramid_tm
        lambda r: get_tm_session(session_factory, r.tm),
        'dbsession', reify=True )
