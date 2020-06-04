from contextlib import closing
import pytest
import socket
import time


def get_open_port(host):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind((host, 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_port(host, port, timeout=60):
    while timeout > 0:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.settimeout(1)
            if s.connect_ex((host, port)) == 0:
                return
        time.sleep(1)
        timeout -= 1
    raise RuntimeError(
        "The port %s on host %s didn't become accessible" % (port, host))


@pytest.fixture
def app(tmp_path):
    from troublebox import make_app
    from troublebox.models import Base
    import transaction
    sqlite_path = tmp_path / 'troublebox.sqlite'
    app = make_app(None, **{
        'sqlalchemy.url': 'sqlite:///%s' % sqlite_path})
    sessionmaker = app.registry['dbsession_factory']
    session = sessionmaker()
    Base.metadata.bind = session.bind
    Base.metadata.create_all()
    transaction.commit()
    return app


@pytest.fixture
def testapp(app):
    from webtest import TestApp
    return TestApp(app)


@pytest.fixture
def troublebox_server(app):
    from wsgiref.simple_server import make_server
    import threading
    host = 'localhost'
    port = get_open_port(host)
    server = make_server(host, port, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    wait_for_port(host, port, 5)
    yield server
    server.shutdown()


@pytest.fixture
def sentry_url(troublebox_server):
    return "http://key@%s:%s/31415" % troublebox_server.server_address


@pytest.fixture
def sentry_raven_client(sentry_url):
    from raven import Client
    from raven.transport.http import HTTPTransport
    return Client(sentry_url, transport=HTTPTransport)


@pytest.fixture
def sentry_sdk_client(sentry_url):
    from sentry_sdk.client import Client
    return Client(sentry_url)


def test_raven_capture_message(sentry_raven_client, testapp):
    event_id = sentry_raven_client.captureMessage("foo")
    result = testapp.get('/')
    (item,) = result.html.select('td.event a')
    assert event_id in item.text


def test_sdk_capture_event(sentry_sdk_client, testapp):
    event_id = sentry_sdk_client.capture_event(
        {"message": "foo", "level": "info"})
    sentry_sdk_client.transport._worker.flush(1)
    result = testapp.get('/')
    (item,) = result.html.select('td.event a')
    assert event_id in item.text
