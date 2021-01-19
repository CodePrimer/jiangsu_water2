# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil

import pymysql

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')

with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


map_dir = globalCfg['map_dir']
output_path = globalCfg['output_path']

model_uuid = '6ce5de13-da13-11ea-871a-0242ac110003'
# startDate = '2019-01-01 00:00:01'
# endDate = '2019-12-31 23:59:59'

if __name__ == '__main__':

    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )
    cursor = conn.cursor()
    sqlStr = "SELECT path FROM t_export_image WHERE model_uuid = %s;"
    # sqlData = (model_uuid, startDate, endDate)
    sqlData = model_uuid
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    cursor.close()
    conn.close()

    sqlDirList = []
    for each in sqlRes:
        filePath = each[0]
        dirName = os.path.dirname(filePath).replace('\\', '/')
        dirPath = os.path.join(map_dir, dirName)
        dirPath = dirPath.replace('\\', '/')
        sqlDirList.append(dirPath)

    # 被清除的根目录
    cleanRootPath = os.path.join(output_path, model_uuid)
    cleanRootPath = cleanRootPath.replace('\\', '/')
    cleanDirList1 = os.listdir(cleanRootPath)
    cleanDirList2 = []
    for each in cleanDirList1:
        fullPath = os.path.join(cleanRootPath, each)
        fullPath = fullPath.replace('\\', '/')
        cleanDirList2.append(fullPath)
    count = 0
    for each in cleanDirList2:
        if each not in sqlDirList:
            shutil.rmtree(each)
            print('rm dir: %s' % each)
            count += 1
    print(count)
    print('Finish')
