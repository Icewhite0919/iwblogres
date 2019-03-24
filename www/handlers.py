import base64
import json
import os
import re
import time
import uuid
from _sha256 import sha256
from hmac import HMAC
from aiohttp import web
from www.apis import APIValueError, APIError
from www.coroweb import get, post
from www.models import User, Comment, Blog, next_id

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')


def next_imgid():
    return '%015d%s001' % (int(time.time() * 1000), uuid.uuid4().hex)


def encrypt_password(password, salt=None):
    if salt is None:
        salt = os.urandom(8)  # 64 bits.

    assert 8 == len(salt)
    assert isinstance(salt, bytes)
    assert isinstance(password, str)

    if isinstance(password, str):
        password = password.encode('UTF-8')

    assert isinstance(password, bytes)

    result = password
    for i in range(10):
        result = HMAC(result, salt, sha256).digest()
    return salt + result


def validate_password(hashed, input_password):
    return hashed == encrypt_password(input_password, salt=hashed[:8])


@get('/')
async def index(request):
    users = await User.findAll()
    return {
        '__template__': 'index.html',
        'users': users
    }


@post('/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd:
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    en_passwd = encrypt_password(passwd)
    print(uid, name, email, base64.b64encode(en_passwd).decode())
    user = User(id=uid, name=name.strip(), email=email, passwd=base64.b64encode(en_passwd).decode())
    await user.save()
    return '添加成功'


@post('/blogs')
async def api_add_blog(*, name, intro, body, img):
    uid = next_id()
    body = base64.b64encode(body.encode()).decode() #存
    with open('./static/images/blogimg/' + uid + '.png', 'wb') as store:
        store.write(base64.b64decode(img[22:].encode()))
    # body = base64.b64decode(body).decode() #取
    # blog = Blog(id=uid, user_id='null', user_image='null',user_name='冰白', name=name, summary=intro, content=body)
    # await blog.save()


@post('/imgurl')
async def saveimg(**kw):
    imgid = next_imgid()
    with open('./static/images/blogimg/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''), 'wb') as store:
        store.write(kw['upload'].file.read())
    return dict(uploaded=1, url='/img/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''))


@get('/img/{filename}')
async def staticGetter(filename):
    with open('./static/images/blogimg/' + filename, 'rb') as f:
        return f.read()


@get('/test')
async def test(request):
    return{
        '__template__': 'blog_add.html'
    }

