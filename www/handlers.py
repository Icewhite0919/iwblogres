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
    comments = await Comment.findAll(['blog_id','show'], [id, True])
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
    blog = Blog(id=uid, user_id='null', user_image='138649796585137407.jpg',user_name='冰白', name=name, summary=intro, content=body, img=uid+'.png')
    await blog.save()


@post('/imgurl')
async def saveimg(**kw):
    imgid = next_imgid()
    with open('./static/images/blogimg/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''), 'wb') as store:
        store.write(kw['upload'].file.read())
    return dict(uploaded=1, url='/img/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''))


@get('/img/{dictionary}/{filename}')
async def staticGetter(*, dictionary, filename):
    with open('./static/images/'+ dictionary + '/' + filename, 'rb') as f:
        return f.read()


@get('/userimg/{filename}')
async def user_img_getter(filename):
    with open('./static/images/userimg/' + filename, 'rb') as f:
        return f.read()


@get('/test')
async def test(request):
    blogs = await Blog.findAll()
    blog = blogs[0]
    comments = await Comment.findAll(where=['blog_id', 'show'], args=[blog.id, True])
    # blogs[0].created_at = datetime_filter(blogs[0].created_at)
    return{
        '__template__': 'page.html',
        'blog': blog,
        'comments': comments
    }


@post('/comments')
async def api_submit_comments(*, blogid, name, email, website, content):
    comment = Comment(blog_id=blogid, user_id='null', user_name=name, user_image='138649796585137407.jpg', content=content)
    await comment.save()

