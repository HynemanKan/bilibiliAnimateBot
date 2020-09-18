import math,json,time,random,traceback,re
import requests
import numpy as np
import cv2
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
#from apscheduler.schedulers.blocking import BlockingScheduler
import settings,db,support


headers={
"User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36"
}

executors = {
    'default': ThreadPoolExecutor(10),
    'processpool': ProcessPoolExecutor(3)
}
#scheduler = BackgroundScheduler()
scheduler = BackgroundScheduler(executors=executors)

def getUserDataByCard(uid):
    apiUrl = "https://api.bilibili.com/x/web-interface/card"
    res = requests.get(apiUrl,{
        "mid":uid,
        "photo":"true"
    },headers=headers).json()
    return res["data"]


def unreadcheck():
    print("check new")
    url = "https://api.vc.bilibili.com/session_svr/v1/session_svr/single_unread"
    cookies = support.get_cookies()
    raw_res = requests.get(url,cookies=cookies,headers=headers)
    res = raw_res.json()
    support.set_cookies(raw_res.cookies)
    #print(res)
    scheduler.add_job(check_unread)
    if res["data"]["unfollow_unread"] >0 and settings.background_unfollow_response:
        pass
    if res["data"]["follow_unread"] >0 and settings.background_follow_response:
        pass

def _analysis_following_data(jsonData):
    #print(jsonData)
    for item in jsonData["data"]["list"]:
        mid = item["mid"]
        sql = "INSERT INTO followings VALUES ({})".format(mid)
        try:
            db.cursor.execute(sql)
            db.mysql.commit()
        except Exception as e:
            print("already insert")



def get_all_following():
    url = "https://api.bilibili.com/x/relation/followings?vmid={}"
    cookies = support.get_cookies()
    uid = db.redisdb.get("bilibili_msg_poster_uid")
    targetUrl = url.format(uid)
    res = requests.get(targetUrl,cookies=cookies,headers=headers).json()
    totalNum = res["data"]["total"]
    pageNum = math.ceil(totalNum/50)
    _analysis_following_data(res)
    url = "https://api.bilibili.com/x/relation/followings?vmid={}&pn={}"
    for pnum in range(2,pageNum+1):
        targetUrl = url.format(uid,pnum)
        res = requests.get(targetUrl,cookies=cookies,headers=headers).json()
        _analysis_following_data(res)


def isFollowing(mid):
    db.mysql.ping(reconnect=True)
    sql = "SELECT * FROM followings WHERE mid={}".format(mid)
    len = db.cursor.execute(sql)
    if len>0:
        return True
    else:
        return False


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


def send_text_msg(receiver_id,msg_content):
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


def get_bangomi_id(name,season,ep,btv_url=True):
    if re.match("[0-9]{4}-[0-9]{2}",season) is None:
        return False,None
    search_url = "http://api.bilibili.com/x/web-interface/search/type"
    cookies_jar = support.get_cookies()
    arg = {
        "search_type":"media_bangumi",
        "keyword":name
    }
    res = requests.get(search_url,arg,cookies=cookies_jar,headers=headers).json()
    #print(res)
    if "result" in res["data"].keys():
        for bangomi in res["data"]["result"]:
            pubtime = bangomi["pubtime"]
            pub_time=time.strftime("%Y-%m",time.localtime(pubtime))
            if pub_time == season:
                for eps in bangomi["eps"]:
                    if eps["index_title"] == str(ep):
                        if btv_url:
                            return True,f"https://b23.tv/ep{eps['id']}"
                        else:
                            return True,eps['id']
    return False,None


def do_answer(event):
    try:
        print(event)
        if event["msg"]["msg_type"]==2:
            content = event["msg"]["content"]
            url = json.loads(content)["url"]
            print("use api to search")
            send_text_msg(
                event["talker_id"],
                f"已收到，正在识别中[doge]"
            )
            api_url = "https://trace.moe/api/search"
            while True:
                try:
                    if settings.useProxies:
                        res = requests.get(api_url, {
                            "url": url
                        }, proxies=settings.proxies, timeout=15)
                    else:
                        res = requests.get(api_url, {
                            "url": url
                        }, timeout=15)
                    res = res.json()
                    break
                except Exception as e:
                    send_text_msg(event["talker_id"], "识番api超时重试中[笑哭]")
            print(res)
            guess_res = res["docs"][0]
            at_time = int(guess_res["at"])
            at_time = f"{round(at_time//60)}:{str(int(at_time%60)).zfill(2)}"
            if guess_res["is_adult"]:
                is_adult_msg = "\n你这个hentai，为啥给我看这个"
            else:
                is_adult_msg=""
            res_text = f"[斜眼笑]识别结果：\n相似度:{round(guess_res['similarity']*100,2)}%\n番名：{guess_res['anime']}\n季度：{guess_res['season']}\n集数：{guess_res['episode']}\t时间轴：{at_time}{is_adult_msg}"
            send_text_msg(event["talker_id"],res_text)
            if guess_res['similarity'] <0.85:
                send_text_msg(event["talker_id"], "好像不太像啊[笑哭]``要不再试试别的办法")
            else:
                state,url = get_bangomi_id(guess_res['anime'],guess_res['season'],guess_res['episode'])
                if state:
                    send_text_msg(event["talker_id"], url)
        elif event["msg"]["msg_type"]==1:
            send_text_msg(
                event["talker_id"],
                f"欢迎使用凉风bot[可爱]\n本机器人支持截图识番剧，请直接发图片给我吧"
            )
    except Exception as e:
        traceback.print_exc()
        send_text_msg(
            event["talker_id"],
            f"好像出错了啊[惊吓],过一会再试吧"
        )

def raise_msg_event(data):
    for msg in data["data"]["session_list"]:
        if msg["talker_id"] != msg["last_msg"]["sender_uid"]:
            continue
        if isFollowing(msg["talker_id"]):
            continue
        udata = getUserDataByCard(msg["talker_id"])
        event={
            "event_type":"personal",
            "talker_id":msg["talker_id"],
            "msg":msg["last_msg"],
            "talker":{
                "is_follow":msg["is_follow"],
                "is_dnd":msg["is_dnd"],
                "uid":msg["talker_id"],
                "following":udata["following"],
                "sex":udata["card"]["sex"],
                "name":udata["card"]["name"],
                "face":udata["card"]["face"],
                "levelInfo":udata["card"]["level_info"],
                "archive_count":udata["archive_count"],
                "article_count": udata["article_count"],
                "followerNum":udata["follower"]
            }
        }
        try:
            scheduler.add_job(do_answer,args=[event])
        except Exception as e:
            traceback.print_exc()



def check_unread():
    ask_ts = db.redisdb.get("bilibili_msg_poster_ack_ts")
    sessions_ts =db.redisdb.get("bilibili_msg_poster_session_ts")
    url_1 = "https://api.vc.bilibili.com/session_svr/v1/session_svr/new_sessions?begin_ts={}&build=0&mobi_app=web"
    url_2 = "https://api.vc.bilibili.com/session_svr/v1/session_svr/ack_sessions?begin_ts={}&build=0&mobi_app=web"
    #url_3 = "https://api.vc.bilibili.com/session_svr/v1/session_svr/single_unread?unread_type=0&build=0&mobi_app=web"
    cookies = support.get_cookies()
    raw_res_1 = requests.get(url_1.format(sessions_ts),headers=headers,cookies=cookies)
    support.set_cookies(raw_res_1.cookies)
    cookies = support.get_cookies()
    raw_res_2 = requests.get(url_2.format(ask_ts),headers=headers,cookies=cookies)
    support.set_cookies(raw_res_2.cookies)
    res_1 = raw_res_1.json()
    res_2 = raw_res_2.json()
    print(res_1)
    #print(res_2)
    if "session_list" in res_1["data"].keys():
        least_msg = res_1["data"]["session_list"][0]
        ack_ts = least_msg["ack_ts"]
        session_ts = least_msg["session_ts"]
        db.redisdb.set("bilibili_msg_poster_ack_ts", ack_ts)
        db.redisdb.set("bilibili_msg_poster_session_ts", session_ts)
        scheduler.add_job(raise_msg_event, args=[res_1])
    if "session_list" in res_2["data"].keys():
        pass



def start_ack():
    url_1 = "https://api.vc.bilibili.com/session_svr/v1/session_svr/get_sessions?session_type=1&group_fold=1&unfollow_fold=0&sort_rule=2&build=0&mobi_app=web"
    url = "https://api.vc.bilibili.com/session_svr/v1/session_svr/update_ack"
    cookies = support.get_cookies()
    raw_res = requests.get(url_1,cookies=cookies,headers=headers)
    support.set_cookies(raw_res.cookies)
    res = raw_res.json()
    least_msg = res["data"]["session_list"][0]
    ack_ts = least_msg["ack_ts"]
    session_ts = least_msg["session_ts"]
    db.redisdb.set("bilibili_msg_poster_ack_ts",ack_ts)
    db.redisdb.set("bilibili_msg_poster_session_ts",session_ts)
    print(ack_ts,session_ts)
    data = {
        "talker_id":db.redisdb.get("bilibili_msg_poster_uid"),
        "session_type":1,
        "ack_seqno":14,
        "build":0,
        "mobi_app":"web",
        "csrf_token":support.get_cookies_value("bili_jct")

    }
    cookies = support.get_cookies()
    requests.post(url,data,cookies=cookies,headers=headers).json()
    support.set_cookies(raw_res.cookies)


def reply_dynamic(target_id,msg):
    send_msg_api = "https://api.bilibili.com/x/v2/reply/add"
    data = {
        "oid": target_id,  # reply_target_id
        "type": "11",
        "plat": "1",
        "jsonp": "jsonp",
        "csrf": support.get_cookies_value("bili_jct"),  # cookies->bili_jct
        "message": msg
    }
    cookies = support.get_cookies()
    res = requests.post(send_msg_api,data,headers=headers,cookies=cookies)
    support.set_cookies(res.cookies)
    print(res.json())


def splitColorFromBlack(img):
    b,g,r = cv2.split(img)
    [rows, cols] = b.shape
    b_count = np.zeros(266)+1
    for i in range(rows):
        for j in range(cols):
            b_count[b[i,j]+5]+=1
    g_count = np.zeros(266)+1
    for i in range(rows):
        for j in range(cols):
            g_count[g[i,j]+5]+=1
    r_count = np.zeros(266)+1
    for i in range(rows):
        for j in range(cols):
            r_count[r[i,j]+5]+=1
    dev_b = b_count[1:]/b_count[:-1]
    dev_g = g_count[1:]/g_count[:-1]
    dev_r = r_count[1:]/r_count[:-1]
    dev = dev_b*dev_g*dev_r
    for x in np.nditer(dev, op_flags=['readwrite']):
        if x <20:
            x[...]=0
        else:
            x[...]=1
    dev = dev[1:]-dev[:-1]
    for x in np.nditer(dev, op_flags=['readwrite']):
        if x <0:
            x[...]=0
    index =list(dev.nonzero()[0])
    if len(index) == 2 and abs(index[0]-index[1])>175:
        return True
    else:
        return False


def anal_dynamic_res(res,first=False):
    last_check = json.loads(db.redisdb.get("bilibili_msg_poster_d_lastCheck"))["last_check"]
    for card in res['data']["cards"]:
        if card["desc"]["topic_board_desc"] == "热门":
            continue
        if card["desc"]["timestamp"] < last_check:
            print(card["desc"]["topic_board_desc"], card["desc"]["timestamp"])
            return False
        card_detail = json.loads(card["card"])
        if 'item' not in card_detail.keys():
            print("no msg body find find ,skip")
            continue
        if "pictures" not in card_detail['item'].keys():
            print("no picture find ,skip")
            continue
        if len(card_detail['item']["pictures"]) > 1:
            print("too many picture find ,skip")
            continue
        width = card_detail['item']["pictures"][0]["img_width"]
        height = card_detail['item']["pictures"][0]["img_height"]
        img_url = card_detail['item']["pictures"][0]["img_src"]
        if height / width > 0.8:
            print(f"picture size:{width}*{height} not like a screen_shot")
            print(img_url)
            continue
        img_ele = requests.get(img_url, headers=headers)
        img = cv2.imdecode(np.frombuffer(img_ele.content, np.uint8), cv2.IMREAD_COLOR)
        if splitColorFromBlack(img):
            print(f"picture is black white")
            print(img_url)
            continue
        time.sleep(5)
        api_url = "https://trace.moe/api/search"
        while True:
            try:
                if settings.useProxies:
                    s_res = requests.get(api_url, {
                        "url": img_url
                    }, proxies=settings.proxies,timeout=15)
                else:
                    s_res = requests.get(api_url, {
                        "url": img_url
                    }, timeout=15)
                break
            except Exception as e:
                traceback.print_exc()
                time.sleep(1)
                print("retry")
        try:
            s_res = s_res.json()
        except Exception as e:
            print("error")
            continue
        if isinstance(s_res,str):
            print("api can't read img error,skip")
            continue
        guess_res = s_res["docs"][0]
        if guess_res["similarity"] < 0.95:
            print(f"similarity:{guess_res['similarity']},too low")
            continue
        else:
            reply_target_id = card["desc"]["rid"]
            print(reply_target_id, img_url)
            at_time = int(guess_res["at"])
            at_time = f"{round(at_time // 60)}:{str(int(at_time % 60)).zfill(2)}"
            state, burl = get_bangomi_id(guess_res['anime'], guess_res['season'], guess_res['episode'])
            if not state:
                burl = ""
            msg = f"人形自走凉彦祖试作型-α\n[热词系列_知识增加]\n自动识番结果（仅供参考）:\n相似度:{round(guess_res['similarity'] * 100, 2)}%\n番名：{guess_res['anime']}\n季度：{guess_res['season']}\n集数：{guess_res['episode']}\t时间轴：{at_time}\n{burl}"
            reply_dynamic(reply_target_id,msg)
    return True

def checkDynamic():
    now = time.time()
    topic_id = 7085462# 阅片无数topic id
    topic_name = "阅片无数"
    url = "https://api.vc.bilibili.com/topic_svr/v1/topic_svr/topic_new"
    arg = {
        "topic_id": topic_id
    }
    cookies = support.get_cookies()
    res = requests.get(url, arg, headers=headers,cookies=cookies)
    support.set_cookies(res.cookies)
    res = res.json()
    state = anal_dynamic_res(res)
    next = res["data"]["offset"]
    while state:
        print("get more")
        url = "https://api.vc.bilibili.com/topic_svr/v1/topic_svr/topic_history"
        arg = {
            "topic_name":topic_name,
            "offset_dynamic_id":next
        }
        cookies = support.get_cookies()
        res = requests.get(url, arg, headers=headers,cookies=cookies)
        support.set_cookies(res.cookies)
        res = res.json()
        state = anal_dynamic_res(res)
        next = res["data"]["offset"]
    db.redisdb.set("bilibili_msg_poster_d_lastCheck", json.dumps({
        "last_check": now
    }))

scheduler.add_job(unreadcheck, 'interval',seconds=settings.background_unread_chuck_per_seconds)
scheduler.add_job(checkDynamic, "interval",minutes=10)
scheduler.add_job(get_all_following)
scheduler.add_job(start_ack)
last_check = time.time()
db.redisdb.set("bilibili_msg_poster_d_lastCheck",json.dumps({
    "last_check":last_check
}))
if __name__ == '__main__':
    #reply_dynamic(82180284,"test,hello world!")
    checkDynamic()
