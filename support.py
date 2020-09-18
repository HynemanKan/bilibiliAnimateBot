import functools, json
import requests.utils
import db

def login_required(func):
    @functools.wraps(func) # 修饰内层函数，防止当前装饰器去修改被装饰函数的属性
    def inner(*args, **kwargs):
        # 从session获取用户信息，如果有，则用户已登录，否则没有登录
        if not db.redisdb.exists("bilibili_msg_poster_cookies"):
            return json.dumps({
                "state":-1,
                "msg":"require login"
            })
        else:
            return func(*args, **kwargs)
    return inner


def get_cookies():
    cookies = json.loads(db.redisdb.get("bilibili_msg_poster_cookies"))
    cookies_jar = requests.utils.cookiejar_from_dict(cookies)
    return cookies_jar


def set_cookies(cookies_jar):
    if db.redisdb.exists("bilibili_msg_poster_cookies"):
        cookies = json.loads(db.redisdb.get("bilibili_msg_poster_cookies"))
    else:
        cookies = {}
    new_cookies = requests.utils.dict_from_cookiejar(cookies_jar)
    for key in new_cookies.keys():
        cookies[key] = new_cookies[key]
    db.redisdb.set("bilibili_msg_poster_cookies",json.dumps(cookies))

def get_cookies_value(name):
    cookies = json.loads(db.redisdb.get("bilibili_msg_poster_cookies"))
    return cookies[name]