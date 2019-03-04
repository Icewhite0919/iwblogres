from www.coroweb import add_routes
import logging;logging.basicConfig(level = logging.INFO)
import jinja2
import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

def index(request):
    return web.Response(body = b'<h1>Icewwhite</h1>', headers={'Content-Type':'text/html'})

async def init(loop):
    app = web.Application(loop = loop)
    app.router.add_route('GET','/',index)
    srv = await loop.create_server(app._make_handler(),'127.0.0.1',9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        return (await handler(request))
    return logger


async def response_factory(app, handler):
    async def response(request):
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            pass


loop = asyncio.get_event_loop()
app = web.Application(loop=loop, middlewares=[
    logger_factory, response_factory
])
# init_jinja2(app, filters=dict(datetime=datetime_filter))
add_routes(app, 'handlers')
# add_static(app)
loop.run_until_complete(init(loop))
loop.run_forever()


