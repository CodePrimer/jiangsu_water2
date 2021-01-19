# -*- coding: utf-8 -*-
"""太湖蓝藻水华月报"""

import os
import sys
import json
import time
import heapq
from datetime import datetime

import pymysql
import numpy as np
import gdal
from PIL import Image, ImageDraw, ImageFont
import skimage.io
import skimage.transform
from docxtpl import DocxTemplate


projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from tools.RasterRander.RgbComposite import RgbComposite
from tools.RasterRander.UniqueValues import UniqueValues

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)

REGION_NAME = ['竺山湖', '梅梁湖', '贡湖', '西部沿岸', '南部沿岸', '湖心区', '东部沿岸', '东太湖']


def thisYearCurrentMonth(startTime, endTime):
    """当前月情况"""

    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    cursor = conn.cursor()
    sqlStr = 'SELECT date,area,region_area,image_uuid FROM ' + globalCfg['database_table_report_taihu_info'] + \
             ' WHERE date BETWEEN %s AND %s AND area > 0 AND is_push = 1;'
    sqlData = (startTime, endTime)
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    cursor.close()
    conn.close()
    print(sqlRes)
    imageUuidList = []
    count = len(sqlRes)     # 当月水华发生次数
    if count == 0:
        print('Cannot Search Enough Algae Product.')
        return None

    regionList = np.zeros(8, dtype=np.float)
    dateList = []
    areaList = []
    for each in sqlRes:
        date = each[0]
        area = each[1]
        region = np.array(list(map(float, each[2].split(','))))
        imageUuid = each[3]

        imageUuidList.append(imageUuid)
        dateList.append(date)
        areaList.append(area)
        regionList += region
    if areaList:
        maxArea = max(areaList)    # 当月最大面积
        regionIndex = heapq.nlargest(3, range(len(regionList)), regionList.take)
        maxRegionStr = '%s、%s和%s' % (REGION_NAME[regionIndex[0]], REGION_NAME[regionIndex[1]], REGION_NAME[regionIndex[2]])
        maxAreaDate = dateList[areaList.index(max(areaList))]
        maxAreaDateStr = '%d月%d日' % (maxAreaDate.month, maxAreaDate.day)        # 当月最大面积发生时间
        meanArea = round(np.mean(np.array(areaList)))      # 当月蓝藻平均面积
    else:
        maxRegionStr = ''
        maxArea = ''
        maxAreaDateStr = ''
        meanArea = ''
    return [count, maxRegionStr, maxArea, maxAreaDateStr, meanArea, imageUuidList]


def lastYearCurrentMonth(startTime, endTime):
    """去年当前月情况"""
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    cursor = conn.cursor()
    sqlStr = 'SELECT date,area,region_area,image_uuid FROM ' + globalCfg['database_table_report_taihu_info'] + \
             ' WHERE date BETWEEN %s AND %s AND area > 0 AND is_push = 1;'
    sqlData = (startTime, endTime)
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    cursor.close()
    conn.close()

    imageUuidList = []
    count = len(sqlRes)  # 当月水华发生次数
    if count == 0:
        print('Cannot Search Enough Algae Product.')
        return None
    regionList = np.zeros(8, dtype=np.float)
    dateList = []
    areaList = []
    for each in sqlRes:
        date = each[0]
        area = each[1]
        region = np.array(list(map(float, each[2].split(','))))
        imageUuid = each[3]

        imageUuidList.append(imageUuid)
        dateList.append(date)
        areaList.append(area)
        regionList += region
    if areaList:
        maxArea = max(areaList)  # 当月最大面积
        regionIndex = heapq.nlargest(3, range(len(regionList)), regionList.take)
        maxRegionStr = '%s、%s和%s' % (REGION_NAME[regionIndex[0]], REGION_NAME[regionIndex[1]], REGION_NAME[regionIndex[2]])
        maxAreaDate = dateList[areaList.index(max(areaList))]
        maxAreaDateStr = '%d月%d日' % (maxAreaDate.month, maxAreaDate.day)  # 当月最大面积发生时间
        meanArea = round(np.mean(np.array(areaList)))  # 当月蓝藻平均面积
    else:
        maxRegionStr = ''
        maxArea = ''
        maxAreaDateStr = ''
        meanArea = ''
    return [count, maxRegionStr, maxArea, maxAreaDateStr, meanArea, imageUuidList]


def paragraph(info1, info2, searchTime2):
    """
    第一段文字叙述
    :param info1: 今年当月信息
    :param info2: 去年当月信息
    :param searchTime2: 搜索结束时间
    :return:
    """
    count1 = info1[0]
    region1 = info1[1]
    maxArea1 = info1[2]
    maxDate1 = info1[3]
    meanArea1 = info1[4]
    count2 = info2[0]
    region2 = info2[1]
    maxArea2 = info2[2]
    maxDate2 = info2[3]
    meanArea2 = info2[4]

    endDate = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S')
    endDateStr = '%d月%d日' % (endDate.month, endDate.day)
    lastYearMonth = '%d年%d月' % (endDate.year-1, endDate.month)

    countCal = count1 - count2
    if countCal > 0:
        countCalStr = '增加%d次' % countCal
    elif countCal < 0:
        countCalStr = '减少%d次' % abs(countCal)
    else:
        countCalStr = '相同'

    maxAreaCal = (maxArea1 - maxArea2) / maxArea2 * 100
    if maxAreaCal > 0:
        maxAreaCalStr = '增加%.1f%%（%s发生最大面积，为%d平方千米）' % (maxAreaCal, maxDate2, maxArea2)
    elif maxAreaCal < 0:
        maxAreaCalStr = '减少%.1f%%（%s发生最大面积，为%d平方千米）' % (abs(maxAreaCal), maxDate2, maxArea2)
    else:
        maxAreaCalStr = '相同'

    meanAreaCal = (meanArea1 - meanArea2) / meanArea2 * 100
    if meanAreaCal > 0:
        meanAreaCalStr = '增加%.1f%%（%s平均面积为%d平方千米/次）' % (meanAreaCal, lastYearMonth, meanArea2)
    elif meanAreaCal < 0:
        meanAreaCalStr = '减少%.1f%%（%s平均面积为%d平方千米/次）' % (abs(meanAreaCal), lastYearMonth, meanArea2)
    else:
        meanAreaCalStr = '相同'

    description = '%d月份（截至%s）卫星遥感共计监测到太湖蓝藻水华现象%d次，分布区域主要集中在%s。当月最大面积为%d平方千米，' \
                  '发生时间为%s，月平均面积为%s平方千米/次；与去年同期相比，发生次数%s，最大面积%s，平均面积%s。' \
                  % (endDate.month, endDateStr, count1, region1, maxArea1, maxDate1, meanArea1, countCalStr,
                     maxAreaCalStr, meanAreaCalStr)

    return description


def exportImage(info1, info2, searchTime1, searchTime2, outTif1, outTif2):
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    cursor1 = conn.cursor()
    uuidList1 = str(tuple(info1[5]))
    sqlStr1 = 'SELECT path FROM ' + globalCfg['database_table_export_image'] + \
              ' WHERE uuid IN %s;' % uuidList1
    cursor1.execute(sqlStr1)
    sqlRes1 = cursor1.fetchall()
    cursor1.close()

    cursor2 = conn.cursor()
    uuidList2 = str(tuple(info2[5]))
    sqlStr2 = 'SELECT path FROM ' + globalCfg['database_table_export_image'] + \
              ' WHERE uuid IN %s;' % uuidList2
    cursor2.execute(sqlStr2)
    sqlRes2 = cursor2.fetchall()
    conn.close()

    # 加载掩膜数据
    maskTifPath = os.path.join(globalCfg['depend_path'], 'taihu', '250', 'taihu_mask_utm[0].tif')
    ds = gdal.Open(maskTifPath, gdal.GA_ReadOnly)
    maskArray = ds.GetRasterBand(1).ReadAsArray()
    ds = None

    map_dir = globalCfg['map_dir']
    # 去年当月tif
    if len(sqlRes2) > 0:
        firstTifPath = os.path.join(map_dir, sqlRes2[0][0])
        firstDs = gdal.Open(firstTifPath, gdal.GA_ReadOnly)
        width = firstDs.RasterXSize
        height = firstDs.RasterYSize
        trans = firstDs.GetGeoTransform()
        proj = firstDs.GetProjection()
        frequencyArray = np.zeros((height, width), dtype=np.float)
        resultArray = np.zeros((height, width), dtype=np.int)
        for each in sqlRes2:
            curTifPath = os.path.join(map_dir, each[0])
            curDs = gdal.Open(curTifPath, gdal.GA_ReadOnly)
            curArray = curDs.GetRasterBand(1).ReadAsArray()
            frequencyArray += curArray
            curDs = None
        # 计算当月天数
        datetime1 = datetime.strptime(searchTime1, '%Y-%m-%d %H:%M:%S')
        datetime2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S')
        deltaDays = (datetime2 - datetime1).days + 1
        frequencyArray = (frequencyArray / deltaDays) * 100
        resultArray[frequencyArray == 0] = 0
        resultArray[np.logical_and(frequencyArray > 0, frequencyArray <= 5)] = 1
        resultArray[np.logical_and(frequencyArray > 5, frequencyArray <= 10)] = 2
        resultArray[frequencyArray > 10] = 3
        resultArray[maskArray == 0] = 65535
        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(outTif1, width, height, 1, gdal.GDT_Float32)
        outDs.SetGeoTransform(trans)
        outDs.SetProjection(proj)
        outDs.GetRasterBand(1).WriteArray(resultArray)
        outDs = None
    else:
        print('Not Found Algae.')
    # 今年当月tif
    if len(sqlRes1) > 0:
        firstTifPath = os.path.join(map_dir, sqlRes1[0][0])
        firstDs = gdal.Open(firstTifPath, gdal.GA_ReadOnly)
        width = firstDs.RasterXSize
        height = firstDs.RasterYSize
        trans = firstDs.GetGeoTransform()
        proj = firstDs.GetProjection()
        frequencyArray = np.zeros((height, width), dtype=np.float)
        resultArray = np.zeros((height, width), dtype=np.int)
        for each in sqlRes1:
            curTifPath = os.path.join(map_dir, each[0])
            curDs = gdal.Open(curTifPath, gdal.GA_ReadOnly)
            curArray = curDs.GetRasterBand(1).ReadAsArray()
            frequencyArray += curArray
            curDs = None
        # 计算当月天数
        datetime1 = datetime.strptime(searchTime1, '%Y-%m-%d %H:%M:%S')
        datetime2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S')
        deltaDays = (datetime2 - datetime1).days + 1
        frequencyArray = (frequencyArray / deltaDays) * 100
        resultArray[frequencyArray == 0] = 0
        resultArray[np.logical_and(frequencyArray > 0, frequencyArray <= 5)] = 1
        resultArray[np.logical_and(frequencyArray > 5, frequencyArray <= 10)] = 2
        resultArray[frequencyArray > 10] = 3
        resultArray[maskArray == 0] = 65535
        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(outTif2, width, height, 1, gdal.GDT_Float32)
        outDs.SetGeoTransform(trans)
        outDs.SetProjection(proj)
        outDs.GetRasterBand(1).WriteArray(resultArray)
        outDs = None
    else:
        print('Not Found Algae.')

    # 出图
    # DateFrame范围
    dataFrameBounds = (197833.762, 3419416.355, 277082.543, 3497440.803)
    tifFileList = [outTif1, outTif2]
    for each in tifFileList:
        # 裁切到模板空间大小
        clipTifPath = os.path.join(os.path.dirname(each), os.path.basename(each).replace('.tif', '_clip.tif'))
        ds = gdal.Warp(clipTifPath, each, format='GTiff', outputBounds=dataFrameBounds, dstNodata=65535,
                       xRes=250, yRes=250)
        ds = None
        # 右下角终止列(2438) 右下角终止行(2407)
        activateWidth = 2388  # 有效列数 2004
        activateHeight = 2351  # 有效行数 1841
        offsetWidth = 51  # 左上角起始列
        offsetHeight = 57  # 左上角起始行

        colorTable = {0: (1, 197, 255), 1: (211, 255, 190), 2: (163, 255, 115), 3: (14, 204, 14)}
        classifyRender = UniqueValues.Render(clipTifPath, colorTable, returnMode='MEM')
        classifyRgbImageObj = Image.fromarray(classifyRender, mode='RGB')
        classifyRgbImageObj = classifyRgbImageObj.resize((activateWidth, activateHeight), Image.NEAREST)
        classifyRgbResize = np.asarray(classifyRgbImageObj)
        bgLocation = np.logical_and(classifyRgbResize[:, :, 0] == 255, classifyRgbResize[:, :, 1] == 255,
                                    classifyRgbResize[:, :, 2] == 255,)

        modulePngPath = os.path.join(globalCfg['depend_path'], 'taihu', 'mould', 'taihu_algae_month1.png')
        moduleArray = skimage.io.imread(modulePngPath)
        moduleActivateArray = moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, :]

        classifyRgbResizeCopy = np.copy(classifyRgbResize)
        classifyRgbResizeCopy[:, :, 0][bgLocation] = moduleActivateArray[:, :, 0][bgLocation]
        classifyRgbResizeCopy[:, :, 1][bgLocation] = moduleActivateArray[:, :, 1][bgLocation]
        classifyRgbResizeCopy[:, :, 2][bgLocation] = moduleActivateArray[:, :, 2][bgLocation]

        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 0] \
            = classifyRgbResizeCopy[:, :, 0]
        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 1] \
            = classifyRgbResizeCopy[:, :, 1]
        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 2] \
            = classifyRgbResizeCopy[:, :, 2]

        outImagePath = os.path.join(os.path.dirname(each), os.path.basename(each).replace('.tif', '.jpg'))
        skimage.io.imsave(outImagePath, moduleArray[:, :, 0:3].astype(np.uint8))


def executeSql(db_info):
    db_report_name = db_info[0]
    db_monitor_time = db_info[1]
    db_report_type = db_info[2]
    db_process_time = db_info[3]
    db_download_file = db_info[4]
    db_is_deleted = db_info[5]
    db_region = db_info[6]
    db_satellite = db_info[7]
    db_sensor = db_info[8]
    db_model_uuid = db_info[9]

    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    cursor = conn.cursor()
    sqlStr = 'INSERT INTO ' + globalCfg['database_table_report_task'] + \
             ' (report_name,monitor_time,report_type,process_time,download_file,is_deleted,region,satellite,sensor,' \
             'model_uuid) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);'
    sqlData = (db_report_name, db_monitor_time, db_report_type, db_process_time, db_download_file, db_is_deleted,
               db_region, db_satellite, db_sensor, db_model_uuid)
    cursor.execute(sqlStr, sqlData)
    conn.commit()
    cursor.close()
    conn.close()


def main(searchTime1, searchTime2):
    # 计算去年搜索起始时间
    lastYear1 = datetime.strptime(searchTime1, '%Y-%m-%d %H:%M:%S').year - 1
    lastMonth1 = datetime.strptime(searchTime1, '%Y-%m-%d %H:%M:%S').month
    lastDay1 = datetime.strptime(searchTime1, '%Y-%m-%d %H:%M:%S').day
    lastTime1 = datetime(lastYear1, lastMonth1, lastDay1, 0, 1).strftime('%Y-%m-%d %H:%M:%S')
    # 计算去年搜索结束时间
    lastYear2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S').year - 1
    lastMonth2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S').month
    lastDay2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S').day
    lastTime2 = datetime(lastYear2, lastMonth2, lastDay2, 23, 59).strftime('%Y-%m-%d %H:%M:%S')

    # 获取今年当月情况
    monthInfo1 = thisYearCurrentMonth(searchTime1, searchTime2)
    if monthInfo1 is None:
        return
    # 获取去年当月情况
    monthInfo2 = lastYearCurrentMonth(lastTime1, lastTime2)
    if monthInfo2 is None:
        return

    # 输出文件夹
    outputRootDir = os.path.join(globalCfg['output_path'], 'Statistic')
    timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    outputDir = os.path.join(outputRootDir, timeStamp)
    os.makedirs(outputDir)

    # 当前月统计
    outTif1 = os.path.join(outputDir, 'image1.tif')
    outTif2 = os.path.join(outputDir, 'image2.tif')
    outImage1 = os.path.join(outputDir, 'image1.jpg')
    outImage2 = os.path.join(outputDir, 'image2.jpg')

    para1 = paragraph(monthInfo1, monthInfo2, searchTime2)
    exportImage(monthInfo1, monthInfo2, searchTime1, searchTime2, outTif1, outTif2)

    # ======================================================================================
    # 搜索起始时间
    MarchTime = '2020-03-01 00:01:00'

    # 计算去年搜索起始时间
    lastYear1 = datetime.strptime(MarchTime, '%Y-%m-%d %H:%M:%S').year - 1
    lastMonth1 = datetime.strptime(MarchTime, '%Y-%m-%d %H:%M:%S').month
    lastDay1 = datetime.strptime(MarchTime, '%Y-%m-%d %H:%M:%S').day
    lastTime1 = datetime(lastYear1, lastMonth1, lastDay1, 0, 1).strftime('%Y-%m-%d %H:%M:%S')
    # 计算去年搜索结束时间
    lastYear2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S').year - 1
    lastMonth2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S').month
    lastDay2 = datetime.strptime(searchTime2, '%Y-%m-%d %H:%M:%S').day
    lastTime2 = datetime(lastYear2, lastMonth2, lastDay2, 23, 59).strftime('%Y-%m-%d %H:%M:%S')

    # 3月到当前月统计
    # 获取今年当月情况
    monthInfo3 = thisYearCurrentMonth(MarchTime, searchTime2)
    # 获取去年当月情况
    monthInfo4 = lastYearCurrentMonth(lastTime1, lastTime2)

    outTif3 = os.path.join(outputDir, 'image3.tif')
    outTif4 = os.path.join(outputDir, 'image4.tif')
    outImage3 = os.path.join(outputDir, 'image3.jpg')
    outImage4 = os.path.join(outputDir, 'image4.jpg')

    para2 = paragraph(monthInfo3, monthInfo4, searchTime2)
    exportImage(monthInfo3, monthInfo4, MarchTime, searchTime2, outTif3, outTif4)

    # 月报word写出
    # 数据获取
    this_year = str(datetime.strptime(searchTime1, '%Y-%m-%d %H:%M:%S').year)
    this_month = str(datetime.strptime(searchTime1, '%Y-%m-%d %H:%M:%S').month)
    last_year = str(datetime.strptime(MarchTime, '%Y-%m-%d %H:%M:%S').year - 1)
    time_range = '3~%s' % this_month
    paragraph1 = para1
    paragraph2 = para2
    # [count, maxRegionStr, maxArea, maxAreaDateStr, meanArea, imageUuidList]
    count1 = monthInfo1[0]
    count2 = monthInfo2[0]
    count3 = monthInfo3[0]
    count4 = monthInfo4[0]
    max_area1 = monthInfo1[2]
    max_area2 = monthInfo2[2]
    max_area3 = monthInfo3[2]
    max_area4 = monthInfo4[2]
    mean_area1 = monthInfo1[4]
    mean_area2 = monthInfo2[4]
    mean_area3 = monthInfo3[4]
    mean_area4 = monthInfo4[4]

    countCal1 = count1 - count2
    if countCal1 > 0:
        count_cal1 = '+%d' % countCal1
    elif countCal1 < 0:
        count_cal1 = '-%d' % abs(countCal1)
    else:
        count_cal1 = '0'

    countCal2 = count3 - count4
    if countCal2 > 0:
        count_cal2 = '+%d' % countCal2
    elif countCal2 < 0:
        count_cal2 = '-%d' % abs(countCal2)
    else:
        count_cal2 = '0'

    maxAreaCal1 = (max_area1 - max_area2) / max_area2 * 100
    if maxAreaCal1 > 0:
        max_area_cal1 = '+%.1f%%' % maxAreaCal1
    elif maxAreaCal1 < 0:
        max_area_cal1 = '-%.1f%%' % abs(maxAreaCal1)
    else:
        max_area_cal1 = '0%'

    maxAreaCal2 = (max_area3 - max_area4) / max_area4 * 100
    if maxAreaCal2 > 0:
        max_area_cal2 = '+%.1f%%' % maxAreaCal2
    elif maxAreaCal2 < 0:
        max_area_cal2 = '-%.1f%%' % abs(maxAreaCal2)
    else:
        max_area_cal2 = '0%'

    meanAreaCal1 = (mean_area1 - mean_area2) / mean_area2 * 100
    if meanAreaCal1 > 0:
        mean_area_cal1 = '+%.1f%%' % meanAreaCal1
    elif meanAreaCal1 < 0:
        mean_area_cal1 = '-%.1f%%' % abs(meanAreaCal1)
    else:
        mean_area_cal1 = '0%'

    meanAreaCal2 = (mean_area3 - mean_area4) / mean_area4 * 100
    if meanAreaCal2 > 0:
        mean_area_cal2 = '+%.1f%%' % meanAreaCal2
    elif meanAreaCal2 < 0:
        mean_area_cal2 = '-%.1f%%' % abs(meanAreaCal2)
    else:
        mean_area_cal2 = '0%'

    replaceText = {'this_year': this_year, 'this_month': this_month, 'last_year': last_year, 'time_range': time_range,
                   'paragraph1': paragraph1, 'paragraph2': paragraph2, 'count1': count1, 'count2': count2,
                   'count3': count3, 'count4': count4, 'max_area1': max_area1, 'max_area2': max_area2,
                   'max_area3': max_area3, 'max_area4': max_area4, 'mean_area1': mean_area1, 'mean_area2': mean_area2,
                   'mean_area3': mean_area3, 'mean_area4': mean_area4, 'count_cal1': count_cal1,
                   'count_cal2': count_cal2, 'max_area_cal1': max_area_cal1, 'max_area_cal2': max_area_cal2,
                   'mean_area_cal1': mean_area_cal1, 'mean_area_cal2': mean_area_cal2}
    dependDir = globalCfg['depend_path']
    templateDir = os.path.join(dependDir, 'word')
    templatePath = os.path.join(templateDir, 'report_month.docx')
    tpl = DocxTemplate(templatePath)
    tpl.render(replaceText)

    reportName = '%s年%s月太湖蓝藻遥感监测月报' % (this_year, this_month)
    docxName = reportName + '.docx'

    outWordPath = os.path.join(outputDir, docxName)

    replacePic = {"template_picture1.jpg": outImage1, "template_picture2.jpg": outImage2,
                  "template_picture3.jpg": outImage3, "template_picture4.jpg": outImage4}
    for key in replacePic.keys():
        tpl.replace_pic(key, replacePic[key])
    if os.path.exists(outWordPath):
        os.remove(outWordPath)
    tpl.save(outWordPath)

    monitorTime = '%s年%s月' % (this_year, this_month)
    processTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

    db_info = [reportName,
               monitorTime,
               '月报',
               processTime,
               outWordPath,
               0,
               '太湖',
               'EOS',
               'MODIS',
               '6ce5de13-da13-11ea-871a-0242ac110003'
    ]

    executeSql(db_info)


if __name__ == '__main__':

    inputDate1 = sys.argv[1]
    inputTime1 = sys.argv[2]
    inputDate2 = sys.argv[3]
    inputTime2 = sys.argv[4]
    print(inputDate1)
    print(inputTime1)
    print(inputDate2)
    print(inputTime2)

    # 搜索起始时间
    searchTime1 = "%s %s" % (inputDate1, inputTime1)
    # 搜索结束时间
    searchTime2 = "%s %s" % (inputDate2, inputTime2)
    print(searchTime1)
    print(searchTime2)
    main(searchTime1, searchTime2)

    print('Finish')
