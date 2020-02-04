from .models import Event
from json import loads
from pyramid.response import Response
from sqlalchemy import sql
import gzip
import zlib


def api_store_view(request):
    project = int(request.matchdict['project'])
    auth = request.headers.get('X-Sentry-Auth')
    data = request.body
    if request.headers.get('content-encoding') == 'gzip':
        data = gzip.decompress(request.body)
    elif request.headers.get('content-encoding') == 'deflate':
        data = zlib.decompress(request.body)
    if request.content_type in ('application/json', 'application/octet-stream'):
        data = loads(data)
    session = request.dbsession
    event_id = data.pop('event_id')
    _project = int(data.pop('project', project))
    assert _project == project
    session.add(Event(
        event_id=event_id,
        project=project,
        data=data))
    session.flush()
    return Response('OK')


def index_view(request):
    events = (
        request.dbsession.query(Event)
        .order_by(sql.desc(Event.id))
        .limit(5))
    return dict(
        events=events.all())


def includeme(config):
    config.include('pyramid_chameleon')
    config.add_route('index', '/')
    config.add_view(
        index_view,
        route_name='index',
        renderer="troublebox:templates/index.pt")
    config.add_route('api_store', '/api/{project:\\d+}/store/')
    config.add_view(api_store_view, route_name='api_store')
