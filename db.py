import redis
import settings
#import sqlite3
import pymysql

redisdb = redis.Redis(settings.redis_host,
                      settings.redis_port,
                      settings.redis_db,
                      decode_responses=True)

mysql = pymysql.Connect(host=settings.mysql_host,
                        port=settings.mysql_port,
                        user=settings.mysql_username,
                        password=settings.mysql_password,
                        db=settings.mysql_db)
cursor = mysql.cursor()

#sqliteDB = sqlite3.connect("main.db")
#cursor = sqliteDB.cursor()
