import time
import requests
import db
headers={
"User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36"
}
url = "https://api.bilibili.com/pgc/season/index/result"
arg = {
    "season_version":-1,
    "area":-1,
    "is_finish":-1,
    "copyright":-1,
    "season_status":-1,
    "season_month":-1,
    "year":-1,
    "style_id":-1,
    "order":3,
    "st":1,
    "sort":0,
    "page":1,
    "season_type":1,
    "pagesize":20,
    "type":1
}

def insert_db(season_id,title):
    sql = f"INSERT INTO bangumi VALUES({season_id},%s)"
    try:
        db.cursor.execute(sql,(title))
    except Exception as e:
        sql = f"UPDATE bangumi SET title=%s WHERE season_id={season_id}"
        db.cursor.execute(sql,(title))
    db.mysql.commit()



page=1
while True:
    arg["page"]=page
    print(f"get page {page}")
    page+=1
    res = requests.get(url,arg,headers=headers).json()
    if res["data"]["has_next"] == 0:
        break
    for bangomi in res["data"]["list"]:
        title = bangomi["title"]
        season_id = bangomi["season_id"]
        insert_db(season_id,title)
    time.sleep(1)