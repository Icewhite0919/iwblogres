from www.orm import create_pool
from www.models import User, Blog, Comment
import asyncio

async def test(loop):
    await create_pool(loop=loop, user='icewhite', password='2454946495YxL', database='iwblog')
    u = User(name='iwfans', email='fans@test.com', passwd='123456', image='about:blank')
    await u.save()

loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
