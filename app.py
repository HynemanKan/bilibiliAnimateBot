import json,time,random
import requests
import requests.utils
from flask import Flask,render_template,request,redirect
import db,support
from background import scheduler

headers={
"User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36"
}
app = Flask(__name__)

def startBackground():
    if scheduler.state ==1:
        return True
    elif scheduler.state==0:
        scheduler.start()
        return True
    else:
        scheduler.resume()
        return True

@app.route("/")
def index():
    if not db.redisdb.exists("bilibili_msg_poster_cookies"):
        return render_template("index.html")
    else:
        startBackground()
        return redirect("/state")

@app.route("/state")
def state():
    return "<h1>success</h1>"

@app.route('/api/v1/login.json')
def get_login_qr():
    if not db.redisdb.exists("bilibili_msg_poster_cookies"):
        url = "https://passport.bilibili.com/qrcode/getLoginUrl"
        data = requests.get(url,headers=headers).json()
        qr_code_url = data["data"]["url"]
        db.redisdb.set("bilibili_msg_poster_login_auth",data["data"]["oauthKey"],180)
        return json.dumps({
            "state":0,
            "data":{
                "qr_url":qr_code_url,
                "timeout":180
            }
        })
    else:
        return json.dumps({
            "state": -1,
            "msg": "login already"
        })


@app.route("/background")
def background_state():
    print(scheduler.state)
    return str(scheduler.state)

@app.route("/api/v1/loginState.json")
def get_login_state():
    if not db.redisdb.exists("bilibili_msg_poster_cookies"):
        if db.redisdb.exists("bilibili_msg_poster_login_auth"):
            auth = db.redisdb.get("bilibili_msg_poster_login_auth")
            url = "https://passport.bilibili.com/qrcode/getLoginInfo"
            raw_data = requests.post(url,{
                "oauthKey":auth
            },headers=headers)
            data = raw_data.json()
            if isinstance(data["data"],int):
                loginState = data["data"]
            else:
                support.set_cookies(raw_data.cookies)
                url = "https://api.bilibili.com/nav"
                data = requests.get(url, cookies=raw_data.cookies,headers=headers)
                data = data.json()
                db.redisdb.set("bilibili_msg_poster_uid", data["data"]["mid"])
                db.redisdb.set("bilibili_msg_poster_face_url", data["data"]["face"])
                startBackground()
                loginState = 0
            return json.dumps({
                "state": 0,
                "data": {
                    "login_state":loginState,
                }
            })
        else:
            return json.dumps({
                "state": -1,
                "msg":"try login First"
            })
    else:
        return json.dumps({
            "state": 0,
            "data": {
                "login_state": 0,
            }
        })


@app.route("/api/v1/getNums.json")
@support.login_required
def getNums():
    url = "https://api.bilibili.com/x/relation/stat?vmid={}"
    uid = db.redisdb.get("bilibili_msg_poster_uid")
    targetUrl=url.format(uid)
    cookies = support.get_cookies()
    data={}
    print(targetUrl)
    res = requests.get(targetUrl,cookies=cookies,headers=headers).json()
    print(res)
    data["follower"]=res["data"]["follower"]
    url = "http://api.bilibili.com/x/space/upstat?mid={}"
    targetUrl=url.format(uid)
    res = requests.get(targetUrl, cookies=cookies,headers=headers).json()
    data["videoView"]= res["data"]["archive"]["view"]
    data["articleView"]=res["data"]["article"]["view"]
    data["like"] = res["data"]["likes"]
    return json.dumps({
        "state":0,
        "data":data
    })


@app.route("/api/v1/getSelfInfo.json")
@support.login_required
def getSelfInfo():
    url = "https://api.bilibili.com/nav"
    cookies_jar = support.get_cookies()
    res = requests.get(url,cookies=cookies_jar,headers=headers)
    support.set_cookies(res.cookies)
    data = res.json()
    return json.dumps(data)


def gen_id():
    n = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
    out = []
    charlist = "0123456789ACBDEF"
    for char in n:
        e = int(16 * random.random())
        if char == "x":
            out.append(charlist[e])
        elif char == "y":
            out.append(charlist[e & 3 | 8])
        else:
            out.append(char)
    return "".join(out)


@app.route("/api/v1/send_text_msg.json",methods=["POST"])
@support.login_required
def send_text_msg():
    receiver_id = request.form["receiver_id"]
    msg_content = request.form["msg_content"]
    uid = db.redisdb.get("bilibili_msg_poster_uid")
    cookies_jar = support.get_cookies()
    url = "https://api.vc.bilibili.com/web_im/v1/web_im/send_msg"
    data = {
        "msg[sender_uid]":uid,
        "msg[receiver_id]":receiver_id,
        "msg[receiver_type]":1,
        "msg[msg_type]":1,
        "msg[msg_status]":0,
        "msg[content]": json.dumps({
            "content":msg_content
        }),
        "msg[timestamp]":int(time.time()),
        "msg[dev_id]":gen_id(),
        "build":0,
        "mobi_app":"web",
        "csrf_token":support.get_cookies_value("bili_jct")
    }
    res = requests.post(url,data,cookies=cookies_jar,headers=headers).json()
    return json.dumps(res)


@app.route("/api/v1/send_msg.json",methods=["POST"])
@support.login_required
def send_msg():
    receiver_id = request.form["receiver_id"]
    msg_type = request.form["msg_type"]
    uid = db.redisdb.get("bilibili_msg_poster_uid")
    msg = request.form["msg"]
    cookies_jar = support.get_cookies()
    url = "https://api.vc.bilibili.com/web_im/v1/web_im/send_msg"
    data = {
        "msg[sender_uid]":uid,
        "msg[receiver_id]":receiver_id,
        "msg[receiver_type]":1,
        "msg[msg_type]":msg_type,
        "msg[msg_status]":0,
        "msg[content]":msg,
        "msg[timestamp]":int(time.time()),
        "msg[dev_id]":gen_id(),
        "build":0,
        "mobi_app":"web",
        "csrf_token":support.get_cookies_value("bili_jct")
    }
    res = requests.post(url,data,cookies=cookies_jar,headers=headers).json()
    return json.dumps(res)

@app.route("/logout")
@support.login_required
def logout():
    db.redisdb.delete("bilibili_msg_poster_cookies")
    return "logout"



if __name__ == '__main__':
    db.redisdb.flushall()
    db.cursor.execute("delete from followings")
    db.mysql.commit()
    app.run("0.0.0.0",8080)
