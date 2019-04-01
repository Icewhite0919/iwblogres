import base64
import hashlib
import json
import os
import re
import time
import uuid
import sendgrid
import logging;logging.basicConfig(level=logging.INFO)

from sendgrid.helpers.mail import *
from aiohttp import web
from _sha256 import sha256
from hmac import HMAC
from www.apis import APIValueError, APIError
from www.config import configs
from www.coroweb import get, post
from www.models import User, Comment, Blog, next_id, Unactived_user, Contact

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
async def api_user_authenticate(request, *, email, passwd):
    if not email:
        raise APIValueError('email', '空邮箱')
    if not passwd:
        raise APIValueError('passwd', '空密码')
    users = await User.findAll('email', [email])
    if len(users) == 0:
        raise APIValueError('email', '用户不存在或邮箱输入有误')
    user = users[0]
    if user.passwd != passwd:
        raise APIValueError('passwd', '密码不正确')
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    return r


@post('/ss')
async def api_user_salt(*, email):
    user = await User.findAll('email',email)
    if len(user) == 0:
        return base64.b64encode(os.urandom(8)).decode()
    else:
        return base64.b64encode(base64.b64decode(user[0].passwd.encode())[:8]).decode()


@post('/print')
async def api_print_test(**kw):
    print(kw['ss'])


@post('/signout')
def api_user_signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


@post('/registe')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd:
        raise APIValueError('passwd')
    users = await User.findAll('email', [email])
    if len(users) > 0:
        return '您的邮箱已经被使用了呢，如果被人恶意注册请联系站主，站主邮箱是724900477@qq.com~'
    users = await Unactived_user.findAll('email', [email])
    if len(users) > 0:
        for u in users:
            if ((time.time()-u.created_at) // 60) < 15:
                return '您的邮箱已经注册，请在规定时间内点击邮箱链接激活~'
    uid = next_id()
    try:
        sg = sendgrid.SendGridAPIClient(apikey='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')
        from_email = Email("icewhite@outlook.com")
        to_email = Email(email=email)
        subject = "[小站账号激活]" + name + "，这里有一封激活账户的邮件！"
        content = Content("text/html", '请点击下面链接激活账户：<a href="http://127.0.0.1:9001/active/'+uid+'">神秘链接</a>')
        mail = Mail(from_email, subject, to_email, content)
        sg.client.mail.send.post(request_body=mail.get())
    except:
        return '发送激活邮件失败，请稍后重试'
    user = Unactived_user(id=uid, name=name.strip(), email=email, passwd=passwd, active_code=uid)
    await user.save()
    return '您已注册成功，请在15分钟内点击发送到您邮箱中的链接激活账户即可登录~'


@post('/blogs')
async def api_add_blog(*, name, intro, body, img):
    uid = next_id()
    with open('./static/images/blogintro/' + uid + '.png', 'wb') as store:
        store.write(base64.b64decode(img[22:].encode()))
    # body = base64.b64decode(body).decode() #取
    blog = Blog(id=uid, user_id='null', user_image='/userimg/138649796585137407.jpg',user_name='冰白', name=name, summary=intro, content=body, img='/blogintro/' + uid+'.png')
    await blog.save()


@post('/blogimg')
async def api_save_img(**kw):
    imgid = next_imgid()
    with open('./static/images/blogimg/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''), 'wb') as store:
        store.write(kw['upload'].file.read())
    return dict(uploaded=1, url='/img/blogimg/' + imgid + '.' + kw['upload'].content_type.replace('image/', ''))


@post('/userimg')
async def api_save_userimg(request, *, img):
    if request.__user__:
        imgid = request.__user__.id
        with open('./static/images/userimg/' + imgid + '.png', 'wb') as store:
            store.write(base64.b64decode(img[22:].encode()))


@post('/username')
async def api_modify_name(request, *, name):
    if request.__user__:
        user = await User.find(request.__user__.id)




@get('/img/{dictionary}/{filename}')
async def api_getter_img(*, dictionary, filename):
    with open('./static/images/'+ dictionary + '/' + filename, 'rb') as f:
        return f.read()


@get('/active/{active_code}')
async def api_user_active(request, *, active_code):
    users = await Unactived_user.findAll('active_code',[active_code])
    if len(users) == 0:
        return '注册验证不存在？请重新注册'
    for u in users:
        if ((time.time()-u.created_at) // 60) < 15:
            user = User(id=u.id, email=u.email, passwd=u.passwd, name=u.name,
                        created_at=u.created_at, image='/userimg/' + u.id + '.png')
            with open('./static/images/userimg/' + u.id + '.png', 'wb') as store:
                with open('./static/images/userimg/default.jpg', 'rb') as copy:
                    store.write(copy.read())
            rows = await u.remove()
            if rows == 1:
                await user.save()
                return '激活成功啦，快去登录吧~！'
    return '注册验证不存在或验证时间已过？请再试一次吧~！'


@post('/comments')
async def api_submit_comments(request, *, blogid, name, email, website, content):
    if not name or not email or not content:
        return '请检查名称，电子邮箱，评论是否有未填的信息~'
    comment = Comment(blog_id=blogid, user_id=request.__user__.id if request.__user__ else 'default',
                      user_name=name, user_image=request.__user__.image if request.__user__ else '/userimg/default.jpg',
                      user_website=website, user_email=email, content=content)
    await comment.save()
    return '评论成功~等待审核=w='


@post('/contact')
async def api_submit_contact(*, email, name, content):
    if not email or not name or not content:
        return '请检查名称，电子邮箱，建议是否有未填的信息~'
    uid = next_id()
    contact = Contact(id=uid, email=email, name=name, content=content, created_at=time.time())
    await contact.save()
    return '感谢提议，如果联系方式没有错误我将在不久的将来给你回复~！'


@post('/search')
async def api_article_search(request,*, keyword):
    blogs = iter(await Blog.findAll(where=['name'], args=["like '%"+ keyword +"%'"],
                                    union=[['summary'], ["like '%"+ keyword +"%'"]],
                                    like=True))
    news = await Blog.findAll(orderBy='`created_at` DESC', limit=3)
    rows = []
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


@get('/user')
async def api_user_info(request):
    news = await Blog.findAll(orderBy='`created_at` DESC', limit=3)
    return {
        '__template__': '__user__.html',
        'news': news
    }

#
# @post('/username')
# async def api_user_name(request, *, passwd, name):
#     user = User.find(request.__user__.id)
#     if user:
#
