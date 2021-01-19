# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import uuid
from ftplib import FTP
from datetime import datetime

curPath = os.path.abspath(os.path.dirname(__file__))
projDir = os.path.split(curPath)[0]
sys.path.append(projDir)

from tools.MySqlCustom import SQLStringInterface
from tools.MySqlCustom import executeSql

FTP_URL = '192.168.50.67'
FTP_PORT = 41
FTP_USERNAME = 'water'
FTP_PASSWORD = 'jshj2020@com'

FTP_DOWNLOAD_DIR = '/mnt/resource/EsriFtp'
MYSQL_TABLE_NAME = 't_esri_ftp_download'

SQL_QUERY_ESRI_FTP_TABLE = 'SELECT * FROM t_esri_ftp_download WHERE file_name={file_name};'
SQL_INSERT_ESRI_FTP_TABLE = 'INSERT INTO t_esri_ftp_download (uuid,file_name,satellite,sensor,level,resolution,' \
                            'acquire_time,zone1,zone2,file_type,ftp_path,download_path,process_time) VALUES {values};'

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def main(sensorParam, resParam, zoneParam1, zoneParam2, delayDays):
    # 连接ftp
    ftp = FTP()
    ftp.connect(FTP_URL, FTP_PORT)
    ftp.login(FTP_USERNAME, FTP_PASSWORD)
    print('Connect FTP %s successful.' % FTP_URL)

    # ESRI FTP 文件堆放规则：年份yyyy/传感器sensor/数据

    # 当前年份
    currentYear = str(datetime.now().year)
    yearDirPath = '/%s' % currentYear
    ftp.cwd(yearDirPath)
    sensorList = ftp.nlst()  # 传感器列表
    print(sensorList)

    sqlLoginInfo = {'host': globalCfg['database_host'],
                    'dbname': globalCfg['database'],
                    'user': globalCfg['database_user'],
                    'pwd': globalCfg['database_passwd'],
                    'port': globalCfg['database_port']}

    for sensor in sensorList:
        if sensor != sensorParam:
            continue
        sensorDirPath = os.path.join(yearDirPath, sensor)
        ftp.cwd(sensorDirPath)
        fileList = ftp.nlst()  # 文件列表
        for filename in fileList:
            # 文件后缀
            ext = '.%s' % filename.split('.')[-1]
            if ext not in ['.tif']:
                continue
            basename = filename.split('.')[0]
            # if len(basename.split('_')) != 8:
            #     continue
            issue = basename.split('_')[3]  # 期号
            acquireDateTime = datetime.strptime(issue, "%Y%m%d%H%M")
            sat = basename.split('_')[0]  # 卫星
            sen = basename.split('_')[1]  # 传感器
            lv = basename.split('_')[2]  # 数据等级
            res = basename.split('_')[4]  # 分辨率
            zone1 = basename.split('_')[5]  # 区块编号1
            zone2 = basename.split('_')[7]  # 区块编号2
            acquireTime = str(acquireDateTime)  # 数据时间
            path = os.path.join(sensorDirPath, filename)  # ftp上的文件路径

            if resParam != 'default':
                if res != resParam:
                    continue
            if zoneParam1 != 'default':
                if zone1 != zoneParam1:
                    continue
            if zoneParam2 != 'default':
                if zone2 != zoneParam2:
                    continue
            nowDateTime = datetime.now()
            deltaSecond = (nowDateTime - acquireDateTime).total_seconds()
            deltaHour = deltaSecond / 3600
            if delayDays != 'default':
                if deltaHour > (int(delayDays) * 24):  # 不在有效时间范围内的数据不进行处理
                    continue

            # ============判断下载记录是否存在============================
            sqlData = {'file_name': filename}
            sqlStr = SQLStringInterface(SQL_QUERY_ESRI_FTP_TABLE, sqlData)
            # print(sqlStr)
            sqlRes = executeSql(sqlLoginInfo, sqlStr)
            print(sqlRes)
            if len(sqlRes) != 0:
                continue

            # =====================数据下载==============================
            downloadDir = os.path.join(FTP_DOWNLOAD_DIR, sat)
            if not os.path.exists(downloadDir):
                os.makedirs(downloadDir)
            downloadFilePath = os.path.join(downloadDir, filename)
            ftpFp = open(downloadFilePath, 'wb')
            file_handle = ftpFp.write
            ftp.set_debuglevel(0)
            ftp.retrbinary('RETR %s' % path, file_handle, 1024)
            downloadFileSize = os.path.getsize(downloadFilePath)
            if downloadFileSize == 0:
                print('Download Failed: %s' % filename)
                ftpFp.close()
                os.remove(downloadFilePath)
            else:
                print('Download Success: %s' % filename)
                ftpFp.close()
                # =====================数据入库==============================
                db_uuid = str(uuid.uuid4())
                db_process_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                sqlData = {'values': (db_uuid, filename, sat, sen, lv, res, acquireTime, zone1, zone2, ext, path,
                                      downloadFilePath, db_process_time)}
                sqlStr = SQLStringInterface(SQL_INSERT_ESRI_FTP_TABLE, sqlData)
                # print(sqlStr)
                executeSql(sqlLoginInfo, sqlStr)
                print('Insert SQL Success.')
    # 退出ftp
    ftp.quit()


if __name__ == '__main__':

    sensorParam = sys.argv[1]   # 查询的传感器名称 不可缺省
    resParam = sys.argv[2]      # 查询的分辨率 缺省填default
    zoneParam1 = sys.argv[3]    # 查询的区域号码1 缺省填default
    zoneParam2 = sys.argv[4]    # 查询的区域号码2 缺省填default
    delayDays = sys.argv[5]     # 向前推移的天数 缺省填default

    main(sensorParam, resParam, zoneParam1, zoneParam2, delayDays)

    print('Finish')