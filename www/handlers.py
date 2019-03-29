import base64
import hashlib
import json
import os
import re
import time
import uuid

from aiohttp import web
import logging;logging.basicConfig(level=logging.INFO)

from _sha256 import sha256
from hmac import HMAC
from www.apis import APIValueError, APIError
from www.config import configs
from www.coroweb import get, post
from www.models import User, Comment, Blog, next_id

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
COOKIE_NAME = 'iwsession'
_COOKIE_KEY = configs.session.secret


def user2cookie(user, max_age):
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


async def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None


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
    blogs = iter(await Blog.findAll())
    rows = []
    news = await Blog.findAll(orderBy='`created_at` DESC', limit=3)
    while True:
        try:
            rows.append([])
            rows[-1].append(next(blogs))
            rows[-1].append(next(blogs))
        except StopIteration:
            if len(rows[-1]) == 0:
                rows.pop(-1)
            break
    return {
        '__template__': '__index__.html',
        'rows': rows,
        'news': news
    }


@get('/article/{id}')
async def api_article_getter(*, id):
    blog = await Blog.find(id)
    comments = await Comment.findAll(['blog_id', 'show'], [id, True])
    news = await Blog.findAll(orderBy='`created_at` DESC', limit=3)
    return {
        '__template__': '__article__.html',
        'article': blog,
        'comments': comments,
        'comments_nums': len(comments),
        'news': news
    }


@get('/about')
async def api_about_getter(request):
    news = await Blog.findAll(orderBy='`created_at` DESC', limit=3)
    return {
        '__template__': '__about__.html',
        'news': news
    }


@get('/contact')
async def api_contact_getter(request):
    news = await Blog.findAll(orderBy='`created_at` DESC', limit=3)
    return {
        '__template__': '__contact__.html',
        'news': news
    }


@post('/authenticate')
async def api_user_authenticate(*,email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = await User.findAll('email', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    if not validate_password(base64.b64decode(user.passwd.encode()), passwd):
        raise APIValueError('passwd', 'Invalid password.')
    return {
        '__template__': '__index__.html',
        '__auth__': user
    }


@get('/signout')
def api_user_signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


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
    print(name, intro, body)
    with open('./static/images/blogintro/' + uid + '.png', 'wb') as store:
        store.write(base64.b64decode(img[22:].encode()))
    # body = base64.b64decode(body).decode() #取
    blog = Blog(id=uid, user_id='null', user_image='/userimg/138649796585137407.jpg',user_name='冰白', name=name, summary=intro, content=body, img='/blogintro/' + uid+'.png')
    await blog.save()


@post('/imgurl')
async def api_save_img(**kw):
    imgid = next_imgid()
    with open('./static/images/blogimg/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''), 'wb') as store:
        store.write(kw['upload'].file.read())
    return dict(uploaded=1, url='/img/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''))


@get('/img/{dictionary}/{filename}')
async def staticGetter(*, dictionary, filename):
    with open('./static/images/'+ dictionary + '/' + filename, 'rb') as f:
        return f.read()


@post('/comments')
async def api_submit_comments(*, blogid, name, email, website, content):
    comment = Comment(blog_id=blogid, user_id='null', user_name=name, user_image='138649796585137407.jpg', content=content)
    await comment.save()

