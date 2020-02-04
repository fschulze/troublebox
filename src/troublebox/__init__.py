__version__ = "0.1.0"


def make_app(global_config, **settings):
    from pyramid.config import Configurator

    with Configurator(settings=settings) as config:
        config.include('.models')
        config.include('.app')
        config.scan()
    return config.make_wsgi_app()
