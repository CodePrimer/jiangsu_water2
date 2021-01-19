# -*- coding: utf-8 -*-
"""
简报信息生成
1.存入数据库t_water_report_taihu_quick表中
2.生成word，保存在outputDir
"""

import os
import sys
import time
import json
import uuid
import shutil

import pymysql
from docxtpl import DocxTemplate

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from scripts.taihu_algae_ndvi_export_image import exportImage
from tools.RasterRander.UniqueValues import UniqueValues

LAKE_REGION_NAME = {"zhushanhu": "竺山湖",
                    "meilianghu": "梅梁湖",
                    "gonghu": "贡湖",
                    "westCoast": "西部沿岸",
                    "southCoast": "南部沿岸",
                    "centerLake": "湖心区",
                    "eastCoast": "东部沿岸",
                    "eastTaihu": "东太湖"}

TILE_LEVEL = '8-13'

globalCfgPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def exportWord(jsonPath, productUuid):

    # 解析当前json中信息
    with open(jsonPath, 'r') as f:
        jsonData = json.load(f)
    cloud = jsonData['cloud']       # 云量信息
    totalArea = jsonData['totalArea']   # 蓝藻总面积

    # 生成文字所需信息===============================================================
    issue = os.path.basename(jsonPath).split('_')[3]
    year = int(issue[0:4])
    month = int(issue[4:6])
    day = int(issue[6:8])
    hour = int(issue[8:10])
    minute = int(issue[10:12])
    if hour < 12:
        apStr = '上午'
    else:
        apStr = '下午'
    totalPercent = jsonData['totalPercent']   # 蓝藻总占比
    lakeStat = jsonData['lakeStat']   # 蓝藻面积分布区域
    algaeThreshold = jsonData['algaeThreshold']
    lakeRegionList = []
    lakeRegionStr = ''      # 区域描述1
    for key in lakeStat.keys():
        if lakeStat[key] == 1:
            lakeRegionList.append(LAKE_REGION_NAME[key])
    if len(lakeStat) > 0:
        lakeRegionStr = '、'.join(lakeRegionList)
    # 区域描述2
    if len(lakeRegionList) == 0:
        lakeRegionStr2 = ''
    elif len(lakeRegionList) == 1:
        lakeRegionStr2 = lakeRegionList[0]
    else:
        tempList = lakeRegionList[0:-1]
        lakeRegionStr2 = '、'.join(tempList) + '和' + lakeRegionList[-1]

    description = ''    # 未会商报告文字部分
    description2 = ''   # 监测中心每日一报文字部分

    # 1.全云
    if cloud >= 95:
        description = '%d月%d日遥感监测结果显示，太湖%s全部被云层覆盖，无法判断蓝藻聚集情况，未会商。' % (month, day, apStr)
        description2 = '%d月%d日%d时%d分EOS/MODIS卫星遥感影像显示，太湖全部被云层覆盖，无法判断蓝藻聚集情况。' \
                       % (month, day, hour, minute)
    # 2.有云无藻
    elif 5 < cloud < 95 and totalArea == 0:
        description = '%d月%d日遥感监测结果显示，太湖%s部分被云层覆盖，无云区域内未发现蓝藻聚集现象，未会商。' % (month, day, apStr)
        description2 = '%d月%d日%d时%d分EOS/MODIS卫星遥感影像显示，太湖部分湖区被云层覆盖，无云区域内未发现蓝藻聚集现象。' \
                       % (month, day, hour, minute)
    # 3.无云无藻
    elif cloud <= 5 and totalArea == 0:
        description = '%d月%d日遥感监测结果显示，太湖%s未发现蓝藻聚集现象，未会商。' % (month, day, apStr)
        description2 = '%d月%d日%d时%d分EOS/MODIS卫星遥感影像显示，太湖未发现蓝藻聚集现象。' % (month, day, hour, minute)
    # 4.有云有藻
    elif 5 < cloud < 95 and totalArea > 0:
        description = '%d月%d日遥感监测结果显示，太湖%s部分被云层覆盖，在%s发现蓝藻聚集现象，面积约%d平方千米，占太湖总面积的%.1f%%，' \
                      '未会商。' % (month, day, apStr, lakeRegionStr, totalArea, totalPercent)
        description2 = '%d月%d日%d时%d分EOS/MODIS卫星遥感影像显示，太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，' \
                       '主要分布在%s。' % (month, day, hour, minute, totalArea, lakeRegionStr2)
    # 5.无云有藻
    elif cloud <= 5 and totalArea > 0:
        description = '%d月%d日遥感监测结果显示，太湖%s在%s发现蓝藻聚集现象，面积约%d平方千米，占太湖总面积的%.1f%%，未会商。' \
                      % (month, day, apStr, lakeRegionStr, totalArea, totalPercent)
        description2 = '%d月%d日%d时%d分EOS/MODIS卫星遥感影像显示，太湖发现蓝藻聚集面积约%d平方千米，' \
                       '主要分布%s。' % (month, day, hour, minute, totalArea, lakeRegionStr2)
    else:
        pass

    print(description)
    print(description2)

    # 生成word====================================================
    # 简报word生成
    dependDir = globalCfg['depend_path']
    templateDir = os.path.join(dependDir, 'word')
    templatePath = os.path.join(templateDir, 'report_quick.docx')
    tpl = DocxTemplate(templatePath)
    replaceText = {
        "content": description
    }
    tpl.render(replaceText)

    outputDir = os.path.dirname(jsonPath)
    jsonBaseName = os.path.basename(jsonPath)

    outWordName = jsonBaseName.replace('.json', '_quick.docx')
    outWordPath = os.path.join(outputDir, outWordName)

    picturePath1 = os.path.join(outputDir, jsonBaseName.replace('.json', '_reportImg1_noPoints.jpg'))
    picturePath2 = os.path.join(outputDir, jsonBaseName.replace('.json', '_reportImg2.jpg'))
    if not (os.path.exists(picturePath1) and os.path.exists(picturePath2)):
        print('Cannot Find JPG File!!!')
        return
    replacePic = {
        "template_picture1.jpg": picturePath1,
        "template_picture2.jpg": picturePath2
    }
    for key in replacePic.keys():
        tpl.replace_pic(key, replacePic[key])
    if os.path.exists(outWordPath):
        os.remove(outWordPath)
    tpl.save(outWordPath)

    # 每日一报word生成
    templatePath2 = os.path.join(templateDir, 'report_jsem.docx')
    tpl2 = DocxTemplate(templatePath2)
    replaceText2 = {
        "content": description2,
        "year": str(year),
        "mm": str(month),
        "dd": str(day)
    }
    tpl2.render(replaceText2)

    outWordName2 = jsonBaseName.replace('.json', '_jsem.docx')
    outWordPath2 = os.path.join(outputDir, outWordName2)
    replacePic2 = {
        "template_picture1.jpg": picturePath1,
    }
    for key in replacePic2.keys():
        tpl2.replace_pic(key, replacePic2[key])
    if os.path.exists(outWordPath2):
        os.remove(outWordPath2)
    tpl2.save(outWordPath2)

    # 信息入库t_water_report_taihu_quick====================================================
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    # 先查询数据库是否有这期数据
    cursor = conn.cursor()
    sqlStr = 'SELECT * FROM ' + globalCfg['database_table_report_taihu_quick'] + \
             ' WHERE image=%s and is_deleted=0;'
    algaeTifName = os.path.basename(jsonPath).replace('.json', '.tif')
    cursor.execute(sqlStr, algaeTifName)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        # 更新
        db_image = algaeTifName
        db_description = description
        db_image1 = picturePath1.replace('\\', '/').replace('/mnt/resource/', '')
        db_image2 = picturePath2.replace('\\', '/').replace('/mnt/resource/', '')
        db_time_modify = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        sqlStr = 'UPDATE ' + globalCfg['database_table_report_taihu_quick'] + \
            ' SET description=%s,image1=%s,image2=%s,time_modify=%s WHERE image=%s;'
        sqlData = (db_description, db_image1, db_image2, db_time_modify, db_image)
        cursor.execute(sqlStr, sqlData)
        conn.commit()
    else:
        # 插入
        db_uuid = str(uuid.uuid4())
        db_description = description
        db_image1 = picturePath1.replace('\\', '/').replace('/mnt/resource/', '')
        db_image2 = picturePath2.replace('\\', '/').replace('/mnt/resource/', '')
        db_image = algaeTifName
        sqlStr = 'INSERT INTO ' + globalCfg['database_table_report_taihu_quick'] + \
            ' (uuid,description,image1,image2,image) VALUES (%s,%s,%s,%s,%s);'
        sqlData = (db_uuid, db_description, db_image1, db_image2, db_image)
        cursor.execute(sqlStr, sqlData)
        conn.commit()

    # 更新t_export_image表信息
    sqlStr = 'SELECT * FROM ' + globalCfg['database_table_export_image'] + \
             ' WHERE uuid=%s and is_deleted=0;'
    cursor.execute(sqlStr, productUuid)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        sqlStr = 'UPDATE ' + globalCfg['database_table_export_image'] + \
            ' SET area=%s,threshold=%s WHERE uuid=%s;'
        sqlData = (totalArea, algaeThreshold, productUuid)
        cursor.execute(sqlStr, sqlData)
        conn.commit()
    else:
        pass
    cursor.close()
    conn.close()

    # 更新切片==============================================================
    tileDict = {}
    basename = '_'.join(jsonBaseName.split('_')[0:7])
    # 1.蓝藻产品切片
    algaeTifPath = os.path.join(outputDir, jsonBaseName.replace('.json', '.tif'))
    algaeTifRender = os.path.join(outputDir, jsonBaseName.replace('.json', '_render.tif'))
    colorTable = {1: (255, 251, 0)}
    UniqueValues.Render(algaeTifPath, colorTable, returnMode='GEOTIFF', outputPath=algaeTifRender, isAlpha=True)
    tileDict['taihu_algae_ndvi'] = {'tif': algaeTifRender, 'name': basename + '_taihu_algae_ndvi',
                                    'legendType': '1', 'legendColor': [(255, 251, 0)], 'legendName': ['水华']}

    # 2.蓝藻强度产品切片
    intensityTifPath = os.path.join(outputDir, jsonBaseName.replace('_ndvi.json', '_intensity.tif'))
    intensityTifRender = os.path.join(outputDir, jsonBaseName.replace('_ndvi.json', '_intensity_render.tif'))
    colorTable = {1: (0, 255, 102), 2: (255, 255, 0), 3: (255, 153, 0)}
    UniqueValues.Render(intensityTifPath, colorTable, returnMode='GEOTIFF', outputPath=intensityTifRender, isAlpha=True)
    tileDict['algaeClassify'] = {'tif': intensityTifRender, 'name': basename + '_classify', 'legendType': '1',
                                 'legendColor': [(0, 255, 102), (255, 255, 0), (255, 153, 0)],
                                 'legendName': ['轻度', '中度', '重度']}

    # 调用gdal2tiles工具进行切片
    pythonPath = globalCfg['python_path']
    gdal2tilesPath = globalCfg['gdal2tiles_path']
    tileOutRootDir = globalCfg['tile_server_path']
    for key in tileDict.keys():
        tileTif = tileDict[key]['tif']
        tileOutDir = os.path.join(tileOutRootDir, tileDict[key]['name'])
        if os.path.exists(tileOutDir):
            shutil.rmtree(tileOutDir)
        cmd = '%s %s -z %s -w all %s %s' % (pythonPath, gdal2tilesPath, TILE_LEVEL, tileTif, tileOutDir)
        os.system(cmd)
        os.remove(tileTif)
        tileDict[key]['path'] = tileOutDir


if __name__ == '__main__':
    # jsonPath = r'C:\Users\Administrator\Desktop\model\output\6ce5de13-da13-11ea-871a-0242ac110003\20201112132011\TERRA_MODIS_L2_202006301032_250_00_00_taihu_algae_ndvi.json'
    # productUuid = '544a218e-ed6e-45f0-8a34-e4204c934396'
    jsonPath = sys.argv[1]
    productUuid = sys.argv[2]
    startTime = time.time()
    exportImage(jsonPath)
    exportWord(jsonPath, productUuid)
    endTime = time.time()
    print('Cost %s seconds.' % (endTime - startTime))
