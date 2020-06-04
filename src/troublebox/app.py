from .models import Event
from chameleon import PageTemplate
from chameleon.utils import Markup
from lazy import lazy
from json import dumps, loads
from pprint import pformat
from pyramid.compat import urlparse
from pyramid.httpexceptions import HTTPNotFound
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


exceptions_info_template = PageTemplate('''
    <dl tal:repeat="exception exceptions">
        <dt>${exception.get('module', '')} ${exception.get('type', '')}</dt>
        <dd>${exception.get('value', '')}</dd>
    </dl>''')
frame_template = PageTemplate('''
    <dl class="frame">
        <dt>File <code title="${frame.abs_path}">${frame.filename}</code>, line ${frame.lineno}, in <code title="${frame.module}">${frame.function}</code></dt>
        <dd>
            <pre class="context">${'\\n'.join(frame.pre_context)}\n<strong>${frame.context_line}</strong>\n${'\\n'.join(frame.post_context)}</pre>
            <input type="checkbox" id="frametoggle${id(frame)}" class="togglecontrol">
            <label for="frametoggle${id(frame)}" tal:condition="'vars' in frame">Variables<span class="toggler"></span></label>
            <table class="vars toggleable" tal:condition="'vars' in frame">
                <tbody>
                    <tr tal:repeat="(k, v) frame.vars.items()">
                        <th>${k}</th>
                        <td><pre>${pformat(v)}</pre></td>
                    </tr>
                </tbody>
            </table>
        </dd>
    </dl>''')
div_template = PageTemplate('<div>${value}</div>')
pre_template = PageTemplate('<pre>${value}</pre>')
pre_wrap_template = PageTemplate('<pre style="white-space: pre-wrap">${value}</pre>')
tabled_dict_template = PageTemplate('''
    <table>
        <tbody>
            <tr tal:repeat="(k, v) sorted(value.items())">
                <th>${k}</th>
                <td><pre>${pformat(v)}</pre></td>
            </tr>
        </tbody>
    </table>''')
url_template = PageTemplate('<a href="${url}">${title}</a>')


def render_frame(frame):
    try:
        return frame_template(frame=frame, pformat=pformat)
    except Exception:
        return pre_template(value=pformat(frame))


class Info:
    def __init__(self, title, value, toggle=False, toggled=True):
        self.title = title
        self.value = value
        self.toggle = toggle
        self.toggled = toggled


class EventInfos:
    def __new__(cls, event):
        if event is not None:
            return super().__new__(cls)

    def __init__(self, event):
        self._event = event
        self.data = event.data
        self.event_id = event.event_id
        self.id = event.id
        self.project = event.project
        self.project_title = event.project_title

    @lazy
    def timestamp(self):
        timestamp = self.data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = ' '.join(reversed(timestamp.split('T')))
        if timestamp:
            return timestamp
        return ''

    def iter_infos(self):
        request = self.data.get('request', {})
        url = request.get('url')
        if url is not None:
            yield Markup(url_template(url=url, title=url))
        exceptions = self.data.get('exception', {}).get('values', [])
        if exceptions:
            yield Markup(exceptions_info_template(exceptions=exceptions))
        logentry = self.data.get('logentry')
        if logentry is not None:
            yield Markup(pre_template(value=pformat(logentry)))

    def iter_items(self):
        # make a copy for modification
        data = dict(self.data)
        if 'server_name' in data:
            yield Info('Server Name', data.pop('server_name'))
        platform = data.pop('platform', None)
        if platform:
            yield Info('Platform', platform)
        if 'level' in data:
            yield Info('Level', data.pop('level'))
        data.pop('timestamp', None)
        if 'transaction' in data:
            yield Info('Transaction', data.pop('transaction'))
        request = dict(data.pop('request', {}))
        if 'method' in request:
            yield Info('Request Method', request.get('method'))
        if 'url' in request:
            yield Info(
                'Request URL',
                Markup(url_template(url=request['url'], title=request['url'])))
        if request.get('query_string'):
            qs = request.get('query_string')
            try:
                qs = urlparse.parse_qs(qs)
                yield Info(
                    'Request Query String',
                    Markup(tabled_dict_template(value=qs, pformat=pformat)))
            except Exception:
                yield Info('Request Query String', qs)
        if platform == 'python' and 'values' in data.get('exception', {}):
            exception = dict(data.pop('exception'))
            values = exception.pop('values', [])
            num_values = len(values)
            if num_values > 1:
                title_fmt = 'Exception {}/%s' % num_values
            else:
                title_fmt = 'Exception'
            for index, value in enumerate(values, start=1):
                if 'stacktrace' in value and 'frames' in value['stacktrace']:
                    frames = value['stacktrace'].pop('frames')
                    if not value['stacktrace']:
                        del value['stacktrace']
                    yield Info(
                        title_fmt.format(index) + ' Frames',
                        Markup(''.join(render_frame(x) for x in frames)),
                        toggle=True, toggled=index > 1)
                yield Info(
                    value.pop('type', None),
                    Markup(pre_wrap_template(value=value.pop('value', None))))
                yield Info(
                    title_fmt.format(index) + ' Info',
                    Markup(tabled_dict_template(value=value, pformat=pformat)))
            # in case there are more items
            if exception:
                yield Info(
                    'Exception Meta',
                    Markup(tabled_dict_template(value=exception, pformat=pformat)))
        if 'logentry' in data:
            yield Info(
                'Log Entry',
                Markup(tabled_dict_template(
                    value=data.pop('logentry'), pformat=pformat)))
        if 'logger' in data:
            yield Info('Logger', data.pop('logger'))
        if request:
            yield Info(
                'Request',
                Markup(tabled_dict_template(value=request, pformat=pformat)))
        for key, value in sorted(data.items()):
            yield Info(key, Markup(pre_template(value=pformat(value))))

    @lazy
    def rendered_infos(self):
        return Markup(''.join(div_template(value=x) for x in self.iter_infos()))


def event_view(request):
    project = int(request.matchdict['project'])
    event_id = request.matchdict['event_id']
    event = (
        request.dbsession.query(Event)
        .filter_by(project=project, event_id=event_id)
        .one_or_none())
    if event is None:
        raise HTTPNotFound("The event could not be found")
    return dict(
        dumps=dumps,
        event=EventInfos(event),
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
        events=[EventInfos(e) for e in events],
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
