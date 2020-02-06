from .models import Event
from json import dumps, loads
from pprint import pformat
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


def get_event_infos(event):
    if event is None:
        return None
    infos = dict(
        data=event.data,
        event_id=event.event_id,
        id=event.id,
        project=event.project)
    timestamp = event.data.get('timestamp')
    if isinstance(timestamp, str):
        timestamp = ' '.join(reversed(timestamp.split('T')))
    if timestamp:
        infos['timestamp'] = timestamp
    return infos


def event_view(request):
    project = int(request.matchdict['project'])
    event_id = request.matchdict['event_id']
    event = (
        request.dbsession.query(Event)
        .filter_by(project=project, event_id=event_id))
    return dict(
        dumps=dumps,
        event=get_event_infos(event.one_or_none()),
        pformat=pformat)


def index_view(request):
    events = (
        request.dbsession.query(Event))
    project = None
    if 'project' in request.matchdict:
        project = int(request.matchdict['project'])
        events = events.filter_by(project=project)
    reverse = False
    if 'end' in request.params:
        events = events.filter(Event.id >= int(request.params['end']))
        events = events.order_by(Event.id)
        reverse = True
    else:
        if 'start' in request.params:
            events = events.filter(Event.id <= int(request.params['start']))
        events = events.order_by(sql.desc(Event.id))
    events = events.limit(25)
    start = None
    end = None
    if reverse:
        events = list(reversed(events.all()))
    else:
        events = events.all()
    if events:
        start = events[-1].id
        end = events[0].id
    return dict(
        dumps=dumps,
        events=[get_event_infos(e) for e in events],
        pformat=pformat,
        project=project,
        start=start,
        end=end)


def includeme(config):
    config.include('pyramid_chameleon')
    config.add_route('index', '/')
    config.add_route('project', '/{project:\\d+}')
    config.add_route('event', '/{project:\\d+}/{event_id}')
    config.add_view(
        index_view,
        route_name='index',
        renderer="troublebox:templates/index.pt")
    config.add_view(
        index_view,
        route_name='project',
        renderer="troublebox:templates/index.pt")
    config.add_view(
        event_view,
        route_name='event',
        renderer="troublebox:templates/event.pt")
    config.add_route('api_store', '/api/{project:\\d+}/store/')
    config.add_view(api_store_view, route_name='api_store')
