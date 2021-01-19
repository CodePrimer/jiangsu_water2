# -*- coding: utf-8 -*-
"""
日报信息生成
1.存入数据库t_water_report_taihu表中
2.生成word，保存在outputDir
"""

import os
import sys
import time
import json
import uuid
import shutil
import datetime

import xlsxwriter
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
    cloud = jsonData['cloud']  # 云量信息
    totalArea = jsonData['totalArea']  # 蓝藻总面积

    # 生成文字所需信息===============================================================
    issue = os.path.basename(jsonPath).split('_')[3]
    year = int(issue[0:4])
    mm = int(issue[4:6])
    dd = int(issue[6:8])
    hour = int(issue[8:10])
    minute = int(issue[10:12])
    timeStr = '%d月%d日%d时%d分' % (mm, dd, hour, minute)
    totalPercent = jsonData['totalPercent']  # 蓝藻总百分比
    lakeStat = jsonData['lakeStat']  # 蓝藻面积分布区域
    algaeThreshold = jsonData['algaeThreshold']
    lakeRegionList = []
    for key in lakeStat.keys():
        if lakeStat[key] == 1:
            lakeRegionList.append(LAKE_REGION_NAME[key])
    if len(lakeRegionList) == 0:
        lakeRegionStr = ''
    elif len(lakeRegionList) == 1:
        lakeRegionStr = lakeRegionList[0]
    else:
        tempList = lakeRegionList[0:-1]
        lakeRegionStr = '、'.join(tempList) + '和' + lakeRegionList[-1]
    areaWX = jsonData['adminArea']['wuxi']
    areaCZ = jsonData['adminArea']['changzhou']
    areaSZ = jsonData['adminArea']['suzhou']
    percentWX = jsonData['adminPercent']['wuxi']
    percentCZ = jsonData['adminPercent']['changzhou']
    percentSZ = jsonData['adminPercent']['suzhou']
    areaH = jsonData['highArea']
    areaM = jsonData['midArea']
    areaL = jsonData['lowArea']
    percentH = jsonData['highPercent']
    percentM = jsonData['midPercent']
    percentL = jsonData['lowPercent']

    # 计算期号
    nowDatetime = datetime.datetime.strptime(issue[0:8] + '0000', '%Y%m%d%H%M')
    # 3月以前算上一年期号
    if mm < 3:
        startDatetime = datetime.datetime.strptime(str(year) + '01010000', '%Y%m%d%H%M')
    else:
        startDatetime = datetime.datetime.strptime(str(year) + '03010000', '%Y%m%d%H%M')
    num = (nowDatetime - startDatetime).days + 1    # 期号

    label2 = ''
    label3 = ''

    # 蓝藻日报文字部分===================================================
    # 1.全云
    if cloud >= 95:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖全部被云层覆盖，无法判断蓝藻聚集情况。' % timeStr
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖全部被云层覆盖，无法判断蓝藻聚集情况。' % timeStr
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        templateID = 1
        typeID = 1
    # 2.有云无藻
    elif 5 < cloud < 95 and totalArea == 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖部分湖区被云层覆盖，无云区域内未发现蓝藻聚集现象。' % timeStr
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖部分湖区被云层覆盖，无云区域内未发现蓝藻聚集现象。' % timeStr
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        templateID = 1
        typeID = 2
    # 3.无云无藻
    elif cloud <= 5 and totalArea == 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖未发现蓝藻聚集现象。' % timeStr
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖未发现蓝藻聚集现象。' % timeStr
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        templateID = 1
        typeID = 3
    # 4.有云有藻 面积不大于300
    elif 5 < cloud < 95 and 0 < totalArea <= 300:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图2），' \
                      '占全湖总面积的%.1f%%，主要分布在%s。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                         percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，' \
                       '占全湖总面积的%.1f%%，主要分布在%s。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                       '占%d%%；苏州水域%d平方千米，占%d%%。' \
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                          percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        templateID = 2
        typeID = 4
    # 5.无云有藻 面积不大于300
    elif cloud <= 5 and 0 < totalArea <= 300:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖发现蓝藻聚集面积约%d平方千米（图2），占全湖总面积的%.1f%%，' \
                      '主要分布在%s。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。'\
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                         percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%，' \
                       '主要分布在%s。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                       '占%d%%。'\
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                          percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        templateID = 2
        typeID = 5
    # 6.无云有藻 面积大于300 有高中低聚集区
    elif cloud <= 5 and totalArea > 300 and areaH > 0 and areaM > 0 and areaL > 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖发现蓝藻聚集面积约%d平方千米（图2），占全湖总面积的%.1f%%，' \
                      '主要分布在%s。其中，高、中、低聚集区面积分别约为%d平方千米、%d平方千米和%d平方千米，' \
                      '占蓝藻总聚集面积的%d%%、%d%%和%d%%（表1、图3）。按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaH, areaM, areaL, percentH, percentM,
                         percentL, areaWX, percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%，' \
                       '主要分布在%s。其中，高、中、低聚集区面积分别约为%d平方千米、%d平方千米和%d平方千米，' \
                       '占蓝藻总聚集面积的%d%%、%d%%和%d%%。按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                       '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaH, areaM, areaL, percentH, percentM,
                          percentL, areaWX, percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        label3 = '图3   %d年%d月%d日太湖蓝藻聚集强度分级' % (year, mm, dd)
        templateID = 3
        typeID = 5
    # 7.无云有藻 面积大于300 无高聚集区 有中低聚集区
    elif cloud <= 5 and totalArea > 300 and areaH == 0 and areaM > 0 and areaL > 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖发现蓝藻聚集面积约%d平方千米（图2），占全湖总面积的%.1f%%，' \
                      '主要分布在%s。其中，无高聚集区，中、低聚集区面积分别约为%d平方千米和%d平方千米，占蓝藻总聚集面积的%d%%和%d%%' \
                      '（表1、图3）。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。' \
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaM, areaL, percentM, percentL, areaWX,
                         percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%，' \
                       '主要分布在%s。其中，无高聚集区，中、低聚集区面积分别约为%d平方千米和%d平方千米，占蓝藻总聚集面积的%d%%和%d%%' \
                       '。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                       '占%d%%。' \
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaM, areaL, percentM, percentL, areaWX,
                          percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        label3 = '图3   %d年%d月%d日太湖蓝藻聚集强度分级' % (year, mm, dd)
        templateID = 3
        typeID = 5
    # 8.无云有藻 面积大于300 无高中聚集区 有低聚集区
    elif cloud <= 5 and totalArea > 300 and areaH == 0 and areaM == 0 and areaL > 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖发现蓝藻聚集面积约%d平方千米（图2），占全湖总面积的%.1f%%，' \
                      '主要分布在%s，全部为低聚集区（表1、图3）。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                         percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%，' \
                       '主要分布在%s，全部为低聚集区。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                       '占%d%%；苏州水域%d平方千米，占%d%%。' \
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                          percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        label3 = '图3   %d年%d月%d日太湖蓝藻聚集强度分级' % (year, mm, dd)
        templateID = 3
        typeID = 5
    # 9.有云有藻 面积大于300 有高中低聚集区
    elif 5 < cloud < 95 and totalArea > 300 and areaH > 0 and areaM > 0 and areaL > 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图2），' \
                      '占全湖总面积的%.1f%%，主要分布在%s。其中，高、中、低聚集区面积分别约为%d平方千米、%d平方千米和%d平方千米，' \
                      '占蓝藻总聚集面积的%d%%、%d%%和%d%%（表1、图3）。按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaH, areaM, areaL, percentH, percentM,
                         percentL, areaWX, percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，' \
                       '占全湖总面积的%.1f%%，主要分布在%s。其中，高、中、低聚集区面积分别约为%d平方千米、%d平方千米和%d平方千米，' \
                       '占蓝藻总聚集面积的%d%%、%d%%和%d%%。按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                       '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaH, areaM, areaL, percentH, percentM,
                          percentL, areaWX, percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        label3 = '图3   %d年%d月%d日太湖蓝藻聚集强度分级' % (year, mm, dd)
        templateID = 3
        typeID = 4
    # 10.有云有藻 面积大于300 无高聚集区 有中低聚集区
    elif 5 < cloud < 95 and totalArea > 300 and areaH == 0 and areaM > 0 and areaL > 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图2），' \
                      '占全湖总面积的%.1f%%，主要分布在%s。其中，无高聚集区，中、低聚集区面积约分别约为%d平方千米和%d平方千米，' \
                      '占蓝藻总聚集面积的%d%%和%d%%（表1、图3）。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaM, areaL, percentM, percentL, areaWX,
                         percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，' \
                       '占全湖总面积的%.1f%%，主要分布在%s。其中，无高聚集区，中、低聚集区面积约分别约为%d平方千米和%d平方千米，' \
                       '占蓝藻总聚集面积的%d%%和%d%%。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                       '占%d%%；苏州水域%d平方千米，占%d%%。' \
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaM, areaL, percentM, percentL, areaWX,
                          percentWX, areaCZ, percentCZ, areaSZ, percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        label3 = '图3   %d年%d月%d日太湖蓝藻聚集强度分级' % (year, mm, dd)
        templateID = 3
        typeID = 4
    # 11.有云有藻 面积大于300 无高中聚集区 有低聚集区
    elif 5 < cloud < 95 and totalArea > 300 and areaH == 0 and areaM == 0 and areaL > 0:
        description = '%sEOS/MODIS卫星遥感影像显示（图1），太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图2），' \
                      '占全湖总面积的%.1f%%，主要分布在%s，全部为低聚集区（表1、图3）。按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                         percentSZ)
        description2 = '%sEOS/MODIS卫星遥感影像显示，太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，' \
                       '占全湖总面积的%.1f%%，主要分布在%s，全部为低聚集区。按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                       '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                       % (timeStr, totalArea, totalPercent, lakeRegionStr, areaWX, percentWX, areaCZ, percentCZ, areaSZ,
                          percentSZ)
        label1 = '图1   %d年%d月%d日太湖区域卫星遥感影像' % (year, mm, dd)
        label2 = '图2   %d年%d月%d日太湖蓝藻遥感监测' % (year, mm, dd)
        label3 = '图3   %d年%d月%d日太湖蓝藻聚集强度分级' % (year, mm, dd)
        templateID = 3
        typeID = 4
    else:
        print('No Match Found!!!')
        return
    print(description)

    # 生成文件====================================================
    # 1.生成日报
    replaceText = {'year': year, 'num': num, 'mm': mm, 'dd': dd, 'description': description, 'label1': label1,
                   'label2': label2, 'label3': label3, 'areaH': areaH, 'areaM': areaM, 'areaL': areaL,
                   'totalArea': totalArea, 'percentH': percentH, 'percentM': percentM, 'percentL': percentL}
    dependDir = globalCfg['depend_path']
    templateDir = os.path.join(dependDir, 'word')
    templatePath = os.path.join(templateDir, 'report_daily' + str(templateID) + '.docx')
    tpl = DocxTemplate(templatePath)
    tpl.render(replaceText)

    jsonBaseName = os.path.basename(jsonPath)
    outputDir = os.path.dirname(jsonPath)
    outWordName = jsonBaseName.replace('.json', '.docx')
    outWordPath = os.path.join(outputDir, outWordName)

    picturePath1 = os.path.join(outputDir, jsonBaseName.replace('.json', '_reportImg1_noPoints.jpg'))
    picturePath2 = os.path.join(outputDir, jsonBaseName.replace('.json', '_reportImg2.jpg'))
    picturePath3 = os.path.join(outputDir, jsonBaseName.replace('.json', '_reportImg3.jpg'))
    if not (os.path.exists(picturePath1) and os.path.exists(picturePath2) and os.path.exists(picturePath2)):
        print('Cannot Find JPG File!!!')
        return
    if templateID == 1:
        replacePic = {"template_picture1.jpg": picturePath1}
    elif templateID == 2:
        replacePic = {"template_picture1.jpg": picturePath1, "template_picture2.jpg": picturePath2}
    elif templateID == 3:
        replacePic = {"template_picture1.jpg": picturePath1, "template_picture2.jpg": picturePath2,
                      "template_picture3.jpg": picturePath3}
    else:
        replacePic = {}
    for key in replacePic.keys():
        tpl.replace_pic(key, replacePic[key])
    if os.path.exists(outWordPath):
        os.remove(outWordPath)
    tpl.save(outWordPath)

    # 2.生成推送所需txt第一段文字，剩余两段文字后续添加
    outTxtName = jsonBaseName.replace('.json', '.txt')
    outTxtPath = os.path.join(outputDir, outTxtName)
    with open(outTxtPath, 'w') as f:
        f.write(description2)

    # 3.生成EXCEL
    xls_num = num
    xls_date = str(year) + '/' + str(mm) + '/' + str(dd)
    xls_time = '%s时%s分' % (str(hour), str(minute))
    xls_threshold = str(algaeThreshold)
    xls_ndviMax = str(jsonData['ndviMax'])
    xls_ndviMin = str(jsonData['ndviMin'])
    xls_ndviMean = str(jsonData['ndviMean'])
    xls_boundary = str(jsonData['boundaryThreshold'])
    xls_area = ''
    if typeID == 4 or typeID == 5:
        xls_area = str(totalArea)
    xls_algae_area = ''
    if typeID == 2 or typeID == 3:
        xls_algae_area = '0'
    elif typeID == 4 or typeID == 5:
        xls_algae_area = str(totalArea)
    xls_high = ''
    if totalArea >= 300 and areaH > 0:
        xls_high = str(areaH)
    xls_mid = ''
    if totalArea >= 300 and areaM > 0:
        xls_mid = str(areaM)
    xls_low = ''
    if totalArea >= 300 and areaL > 0:
        xls_low = str(areaL)
    xls_region = lakeRegionStr
    xls_cloud = str(cloud)
    if cloud > 50 and totalArea == 0:
        xls_activate = '0'
    else:
        xls_activate = '1'
    xls_explain = str(typeID)
    xls_weather = ''
    if cloud <= 5:
        xls_cloud_cover = '无覆盖'
    elif cloud >= 95:
        xls_cloud_cover = '全部覆盖'
    else:
        xls_cloud_cover = '部分覆盖'
    xls_total_percent = '%.2f%%' % totalPercent
    xls_intensity_threshold = ''
    if totalArea >= 300:
        xls_intensity_threshold = '%.3f-%.3f,%.3f-%.3f,%.3f-%.3f' \
                                  % (jsonData['ndviMin'], jsonData['insThreshold1'], jsonData['insThreshold1'],
                                     jsonData['insThreshold2'], jsonData['insThreshold2'], jsonData['ndviMax'])
    outXlsxName = jsonBaseName.replace('.json', '.xlsx')
    outXlsxPath = os.path.join(outputDir, outXlsxName)
    if os.path.exists(outXlsxPath):
        os.remove(outXlsxPath)
    workBook = xlsxwriter.Workbook(outXlsxPath)
    sheet = workBook.add_worksheet()
    writeTable = {'A1': '报告期数', 'A2': xls_num,
                  'B1': '日期', 'B2': xls_date,
                  'C1': '时间', 'C2': xls_time,
                  'D1': 'NDVI阈值', 'D2': xls_threshold,
                  'E1': 'NDVI最大值（蓝藻区域）', 'E2': xls_ndviMax,
                  'F1': 'NDVI最小值（蓝藻区域）', 'F2': xls_ndviMin,
                  'G1': 'NDVI均值（蓝藻区域）', 'G2': xls_ndviMean,
                  'H1': '边界缩放', 'H2': xls_boundary,
                  'I1': '面积(km2)无云无藻不填', 'I2': xls_area,
                  'J1': '蓝藻面积（无云无藻填0，全云不填，其他按面积填）', 'J2': xls_algae_area,
                  'K1': '高聚区面积', 'K2': xls_high,
                  'L1': '中聚区面积', 'L2': xls_mid,
                  'M1': '低聚区面积', 'M2': xls_low,
                  'N1': '分布范围（竺山湖、梅梁湖、贡湖、西部沿岸、南部沿岸、东部沿岸和湖心区）', 'N2': xls_region,
                  'O1': '云量', 'O2': xls_cloud,
                  'P1': '是否为有效监测（云量超过50%并且没有监测到蓝藻算无效,1为有效，0为无效）', 'P2': xls_activate,
                  'Q1': '说明（1全云；2有云无藻；3无云无藻；4有云有藻；5无云有藻）', 'Q2': xls_explain,
                  'R1': '天气', 'R2': xls_weather,
                  'S1': '是否被云覆盖（无覆盖、全部覆盖、部分覆盖）', 'S2': xls_cloud_cover,
                  'T1': '水华面积百分比', 'T2': xls_total_percent,
                  'U1': 'NDVI分级阈值', 'U2': xls_intensity_threshold
                  }
    format1 = workBook.add_format({'align': 'center', 'font_size': 10,
                                   'valign': 'vcenter', 'text_wrap': 1})
    for key in writeTable.keys():
        sheet.write(key, writeTable[key], format1)
    sheet.set_row(0, 60)
    sheet.set_column('A:M', 8.85)
    sheet.set_column('N:N', 73)
    sheet.set_column('P:P', 73)
    sheet.set_column('Q:Q', 60)
    sheet.set_column('S:S', 44)
    sheet.set_column('T:T', 15)
    sheet.set_column('U:U', 40)
    workBook.close()

    # 4.生成EXCEL_WX
    writeTable2 = {'A1': '报告期数', 'A2': xls_num,
                   'B1': '日期', 'B2': xls_date,
                   'C1': '时间', 'C2': xls_time,
                   'D1': 'NDVI阈值', 'D2': xls_threshold,
                   'E1': '边界缩放', 'E2': xls_boundary,
                   'F1': '面积(km2)无云无藻不填', 'F2': xls_area,
                   }
    outXlsxWxName = jsonBaseName.replace('.json', '_wx.xlsx')
    outXlsxWxPath = os.path.join(outputDir, outXlsxWxName)
    if os.path.exists(outXlsxWxPath):
        os.remove(outXlsxWxPath)
    workBook2 = xlsxwriter.Workbook(outXlsxWxPath)
    sheet2 = workBook2.add_worksheet()
    format2 = workBook2.add_format({'align': 'center', 'font_size': 10,
                                   'valign': 'vcenter', 'text_wrap': 1})
    for key in writeTable2.keys():
        sheet2.write(key, writeTable2[key], format2)
    sheet.set_row(0, 60)
    sheet.set_column('A:F', 9)
    workBook2.close()

    # 转pdf供前端查看 Windows无法测试===================================================
    outPdfDir = os.path.join(globalCfg['taihu_report_remote'], issue[0:8])
    if not os.path.exists(outPdfDir):
        os.makedirs(outPdfDir)
    cmdStr = 'libreoffice6.3 --headless --convert-to pdf:writer_pdf_Export ' + outWordPath + ' --outdir ' + outPdfDir
    print(cmdStr)
    try:
        os.system(cmdStr)
        print('Convert PDF Success.')
    except Exception as e:
        print(e)

    # 信息入库=========================================================
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    # t_water_report_taihu
    cursor = conn.cursor()
    algaeTifName = os.path.basename(jsonPath).replace('.json', '.tif')
    db_uuid = str(uuid.uuid4())
    db_date = issue[0:4] + '-' + issue[4:6] + '-' + issue[6:8]
    db_number = str(num)
    db_description = description
    db_label1 = ''
    db_label2 = ''
    db_label3 = ''
    db_image1 = ''
    db_image2 = ''
    db_image3 = ''
    db_high_area = ''
    db_mid_area = ''
    db_low_area = ''
    db_total_area = ''
    db_high_percent = ''
    db_mid_percent = ''
    db_low_percent = ''
    db_total_percent = ''
    db_image = algaeTifName
    db_title = '太湖蓝藻水华卫星遥感监测日报'
    db_time_modify = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    if templateID == 1:
        db_label1 = label1
        db_image1 = picturePath1.replace('\\', '/').replace('/mnt/resource/', '')
    elif templateID == 2:
        db_label1 = label1
        db_image1 = picturePath1.replace('\\', '/').replace('/mnt/resource/', '')
        db_label2 = label2
        db_image2 = picturePath2.replace('\\', '/').replace('/mnt/resource/', '')
    elif templateID == 3:
        db_label1 = label1
        db_image1 = picturePath1.replace('\\', '/').replace('/mnt/resource/', '')
        db_label2 = label2
        db_image2 = picturePath2.replace('\\', '/').replace('/mnt/resource/', '')
        db_label3 = label3
        db_image3 = picturePath3.replace('\\', '/').replace('/mnt/resource/', '')
        db_high_area = str(areaH)
        db_mid_area = str(areaM)
        db_low_area = str(areaL)
        db_total_area = str(totalArea)
        db_total_percent = '100.0'
        db_high_percent = str(percentH)
        db_mid_percent = str(percentM)
        db_low_percent = str(percentL)
    else:
        pass
    # 查找是否已存在
    sqlStr = 'SELECT * FROM ' + globalCfg['database_table_report_taihu'] + \
             ' WHERE image=%s and is_deleted=0;'
    cursor.execute(sqlStr, algaeTifName)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        # 更新
        sqlStr = 'UPDATE ' + globalCfg['database_table_report_taihu'] + \
            ' SET date=%s,number=%s,description=%s,image1=%s,image2=%s,image3=%s,label1=%s,label2=%s,label3=%s,' \
            'high_area=%s,mid_area=%s,low_area=%s,total_area=%s,high_percent=%s,mid_percent=%s,low_percent=%s,' \
            'total_percent=%s,title=%s,time_modify=%s WHERE image=%s;'
        sqlData = (db_date, db_number, db_description, db_image1, db_image2, db_image3, db_label1, db_label2, db_label3,
                   db_high_area, db_mid_area, db_low_area, db_total_area, db_high_percent, db_mid_percent,
                   db_low_percent, db_total_percent, db_title, db_time_modify, db_image)
        cursor.execute(sqlStr, sqlData)
        conn.commit()
    else:
        # 插入
        sqlStr = 'INSERT INTO ' + globalCfg['database_table_report_taihu'] + \
                 ' (uuid,date,number,description,image1,image2,image3,label1,label2,label3,high_area,' \
                 'mid_area,low_area,total_area,high_percent,mid_percent,low_percent,total_percent,is_deleted,' \
                 'is_default,image,title,time_modify) VALUES ' \
                 '(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);'
        sqlData = (db_uuid, db_date, db_number, db_description, db_image1, db_image2, db_image3, db_label1, db_label2,
                   db_label3, db_high_area, db_mid_area, db_low_area, db_total_area, db_high_percent,
                   db_mid_percent, db_low_percent, db_total_percent, 0, 0, db_image, db_title, db_time_modify)
        cursor.execute(sqlStr, sqlData)
        conn.commit()

    # t_water_taihu_modis
    # 查找是否已存在
    sqlStr = 'SELECT * FROM ' + globalCfg['database_table_report_taihu_info'] + \
             ' WHERE image_uuid=%s;'
    cursor.execute(sqlStr, productUuid)
    sqlRes = cursor.fetchall()
    db_date = '%s-%s-%s %s:%s' % (issue[0:4], issue[4:6], issue[6:8], issue[8:10], issue[10:12])
    regionArea = jsonData['regionArea']
    area_zsh = str(regionArea['zhushanhu'])
    area_mlh = str(regionArea['meilianghu'])
    area_gh = str(regionArea['gonghu'])
    area_xbya = str(regionArea['westCoast'])
    area_nbya = str(regionArea['southCoast'])
    area_hxq = str(regionArea['centerLake'])
    area_dbya = str(regionArea['eastCoast'])
    area_dth = str(regionArea['eastTaihu'])
    db_region_area = ','.join([area_zsh, area_mlh, area_gh, area_xbya, area_nbya, area_hxq, area_dbya, area_dth])
    if len(sqlRes) > 0:
        # 更新
        sqlStr = 'UPDATE ' + globalCfg['database_table_report_taihu_info'] + \
                 ' SET number=%s,date=%s,ndvi_threshold=%s,ndvi_max=%s,ndvi_min=%s,ndvi_mean=%s,boundary=%s,area=%s,' \
                 'region_area=%s,high_area=%s,mid_area=%s,low_area=%s,cloud=%s,type=%s,is_activate=%s,ndvi_grade=%s ' \
                 'WHERE image_uuid=%s;'
        sqlData = (xls_num, db_date, xls_threshold, xls_ndviMax, xls_ndviMin, xls_ndviMean, xls_boundary,
                   str(totalArea), db_region_area, str(areaH), str(areaM), str(areaL), xls_cloud, xls_explain,
                   xls_activate, xls_intensity_threshold, productUuid)
        cursor.execute(sqlStr, sqlData)
        conn.commit()
    else:
        sqlStr = 'INSERT INTO ' + globalCfg['database_table_report_taihu_info'] + \
                 ' (number,date,ndvi_threshold,ndvi_max,ndvi_min,ndvi_mean,boundary,area,region_area,high_area,' \
                 'mid_area,low_area,cloud,type,is_activate,ndvi_grade,image_uuid) ' \
                 'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);'
        sqlData = (xls_num, db_date, xls_threshold, xls_ndviMax, xls_ndviMin, xls_ndviMean, xls_boundary,
                   str(totalArea), db_region_area, str(areaH), str(areaM), str(areaL), xls_cloud, xls_explain,
                   xls_activate, xls_intensity_threshold, productUuid)
        cursor.execute(sqlStr, sqlData)
        conn.commit()

    # 更新t_export_image信息
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
