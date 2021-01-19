# -*- coding: utf-8 -*-

"""全天报告生成"""
import os
import json
import datetime
import heapq
from decimal import Decimal, ROUND_HALF_UP

from docxtpl import DocxTemplate
import pymysql
import numpy as np

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')

with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)

REGION_NAME = ['竺山湖', '梅梁湖', '贡湖', '西部沿岸', '南部沿岸', '湖心区', '东部沿岸', '东太湖']


def roundCustom(inNum):
    """四舍五入"""
    if not isinstance(inNum, str):
        inNum = str(inNum)
    origin_num = Decimal(inNum)
    answer_num = origin_num.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
    return int(answer_num)


def regionStr(jsonData):
    """主要分布范围文字"""
    # 拼音对应字典
    nameDict = {'zhushanhu': '竺山湖', 'meilianghu': '梅梁湖', 'gonghu': '贡湖', 'westCoast': '西部沿岸',
                'southCoast': '南部沿岸', 'centerLake': '湖心区', 'eastCoast': '东部沿岸', 'eastTaihu': '东太湖'}
    regionData = jsonData['regionArea']
    regionNameList = []
    for key in regionData.keys():
        if regionData[key] > 0:
            regionNameList.append(nameDict[key])
    if len(regionNameList) == 0:
        string = ''
    elif len(regionNameList) == 1:
        string = regionNameList[0]
    else:
        tempList = regionNameList[0:-1]
        string = '、'.join(tempList) + '和' + regionNameList[-1]
    return string


def statusCode(cloud, totalArea, areaH, areaM, areaL):
    """
    上午或下午的状态码
    :param cloud: 云量
    :param totalArea: 总面积
    :param areaH: 高聚区面积
    :param areaM: 中聚区面积
    :param areaL: 低聚区面积
    :return:
    """
    # 1.全云
    if cloud >= 95:
        status = 1
    # 2.有云无藻
    elif 5 < cloud < 95 and totalArea == 0:
        status = 2
    # 3.无云无藻
    elif cloud <= 5 and totalArea == 0:
        status = 3
    # 4.有云有藻 面积不大于300
    elif 5 < cloud < 95 and 0 < totalArea <= 300:
        status = 4
    # 5.无云有藻 面积不大于300
    elif cloud <= 5 and 0 < totalArea <= 300:
        status = 5
    # 6.无云有藻 面积大于300 有高中低聚集区
    elif cloud <= 5 and totalArea > 300 and areaH > 0 and areaM > 0 and areaL > 0:
        status = 6
    # 7.无云有藻 面积大于300 无高聚集区 有中低聚集区
    elif cloud <= 5 and totalArea > 300 and areaH == 0 and areaM > 0 and areaL > 0:
        status = 7
    # 8.无云有藻 面积大于300 无高中聚集区 有低聚集区
    elif cloud <= 5 and totalArea > 300 and areaH == 0 and areaM == 0 and areaL > 0:
        status = 8
    # 9.有云有藻 面积大于300 有高中低聚集区
    elif 5 < cloud < 95 and totalArea > 300 and areaH > 0 and areaM > 0 and areaL > 0:
        status = 9
    # 10.有云有藻 面积大于300 无高聚集区 有中低聚集区
    elif 5 < cloud < 95 and totalArea > 300 and areaH == 0 and areaM > 0 and areaL > 0:
        status = 10
    # 11.有云有藻 面积大于300 无高中聚集区 有低聚集区
    elif 5 < cloud < 95 and totalArea > 300 and areaH == 0 and areaM == 0 and areaL > 0:
        status = 11
    else:
        print('No Match Found!!!')
        return None
    return status


def statusCodeTxt(cloud, totalArea):
    """
    txt文本中上午或下午的状态码
    :param cloud: 云量
    :param totalArea: 总面积
    :param areaH: 高聚区面积
    :param areaM: 中聚区面积
    :param areaL: 低聚区面积
    :return:
    """
    # 1.全云
    if cloud >= 95:
        status = 1
    # 2.有云无藻
    elif 5 < cloud < 95 and totalArea == 0:
        status = 2
    # 3.无云无藻
    elif cloud <= 5 and totalArea == 0:
        status = 3
    # 4.有云有藻
    elif 5 < cloud < 95 and totalArea > 0:
        status = 4
    # 5.无云有藻
    elif cloud <= 5 and totalArea > 0:
        status = 5
    else:
        print('No Match Found!!!')
        return None
    return status


def getTemplateCode(codeAm, codePm):
    if codeAm in [1, 2, 3]:
        Code_AM = '1'
    elif codeAm in [4, 5]:
        Code_AM = '2'
    else:
        Code_AM = '3'
    if codePm in [1, 2, 3]:
        Code_PM = '1'
    elif codePm in [4, 5]:
        Code_PM = '2'
    else:
        Code_PM = '3'
    Code_AMPM = Code_AM + '-' + Code_PM

    codeDict = {'1-1': 1, '1-2': 2, '1-3': 3, '2-1': 4, '2-2': 5, '2-3': 6, '3-1': 7, '3-2': 8, '3-3': 9}

    return codeDict[Code_AMPM]


def searchDate(startTime, endTime):
    """搜索数据"""

    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    cursor = conn.cursor()
    sqlStr = 'SELECT date,area FROM ' + globalCfg['database_table_report_taihu_info'] + \
             ' WHERE date BETWEEN %s AND %s AND area > 0 AND is_push = 1;'
    sqlData = (startTime, endTime)
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    cursor.close()
    conn.close()
    print(sqlRes)

    # ==========返回值初始化=============
    # 太湖蓝藻发生次数
    count = 0
    # 平均聚集面积
    mean_area = 0
    # 最大聚集面积
    max_area = 0
    # 最大面积发生时间
    max_area_date = '3月1日'

    if len(sqlRes) == 0:
        print('Cannot Search Enough Algae Product.')
    else:
        count = len(sqlRes)     # 当月水华发生次数
        dateList = []
        areaList = []
        for each in sqlRes:
            date = each[0]
            area = each[1]
            dateList.append(date)
            areaList.append(area)
        if areaList:
            max_area = max(areaList)    # 当月最大面积
            maxAreaDate = dateList[areaList.index(max(areaList))]
            max_area_date = '%d月%d日' % (maxAreaDate.month, maxAreaDate.day)        # 当月最大面积发生时间
            mean_area = round(np.mean(np.array(areaList)))      # 当月蓝藻平均面积
    return [count, mean_area, max_area, max_area_date]


def wholeDayReport(jsonAm, jsonPm, ensureDirAm, ensureDirPm):
    print(jsonAm)
    print(jsonPm)

    issue = os.path.basename(jsonAm).split('_')[3]

    with open(jsonAm, 'r') as fp:
        jsonDataAm = json.load(fp)
    with open(jsonPm, 'r') as fp:
        jsonDataPm = json.load(fp)

    # 判断条件
    cloudAm = jsonDataAm['cloud']
    cloudPm = jsonDataPm['cloud']
    totalAreaAm = jsonDataAm['totalArea']
    totalAreaPm = jsonDataPm['totalArea']
    highAreaAm = jsonDataAm['highArea']
    midAreaAm = jsonDataAm['midArea']
    lowAreaAm = jsonDataAm['lowArea']
    highAreaPm = jsonDataPm['highArea']
    midAreaPm = jsonDataPm['midArea']
    lowAreaPm = jsonDataPm['lowArea']

    # 所需填充数据==========================================
    # 总面积 totalAreaAm/totalAreaPm
    # 总面积占比 totalPercentAm/totalPercentPm
    totalPercentAm = jsonDataAm['totalPercent']
    totalPercentPm = jsonDataPm['totalPercent']
    # 无锡水域面积 wxAreaAm/wxAreaPm
    wxAreaAm = jsonDataAm['adminArea']['wuxi']
    wxAreaPm = jsonDataPm['adminArea']['wuxi']
    # 常州水域面积 czAreaAm/czAreaPm
    czAreaAm = jsonDataAm['adminArea']['changzhou']
    czAreaPm = jsonDataPm['adminArea']['changzhou']
    # 苏州水域面积 szAreaAm/szAreaPm
    szAreaAm = jsonDataAm['adminArea']['suzhou']
    szAreaPm = jsonDataPm['adminArea']['suzhou']
    # 无锡水域占比 wxPercentAm/wxPercentPm
    wxPercentAm = jsonDataAm['adminPercent']['wuxi']
    wxPercentPm = jsonDataPm['adminPercent']['wuxi']
    # 常州水域占比 czPercentAm/czPercentPm
    czPercentAm = jsonDataAm['adminPercent']['changzhou']
    czPercentPm = jsonDataPm['adminPercent']['changzhou']
    # 苏州水域占比 szPercentAm/szPercentPm
    szPercentAm = jsonDataAm['adminPercent']['suzhou']
    szPercentPm = jsonDataPm['adminPercent']['suzhou']
    # 高中低聚集区百分比
    highPercentAm = jsonDataAm['highPercent']
    midPercentAm = jsonDataAm['midPercent']
    lowPercentAm = jsonDataAm['lowPercent']
    highPercentPm = jsonDataPm['highPercent']
    midPercentPm = jsonDataPm['midPercent']
    lowPercentPm = jsonDataPm['lowPercent']

    # 平均聚集面积 totalAreaMean
    totalAreaMean = roundCustom((totalAreaAm+totalAreaPm)/2.0)
    # 平均聚集面积占比 totalPercentMean
    totalPercentMean = (totalPercentAm+totalPercentPm)/2.0
    # 分布区域 regionStrAm/regionStrPm
    regionStrAm = regionStr(jsonDataAm)
    regionStrPm = regionStr(jsonDataPm)

    # 期号
    year = str(int(issue[0:4]))
    month = str(int(issue[4:6]))
    day = str(int(issue[6:8]))
    # 报告期数
    # 计算期号
    nowDatetime = datetime.datetime.strptime(issue[0:8] + '0000', '%Y%m%d%H%M')
    # 3月以前算上一年期号
    if int(month) < 3:
        startDatetime = datetime.datetime.strptime(str((int(year))) + '01010000', '%Y%m%d%H%M')
    else:
        startDatetime = datetime.datetime.strptime(str(int(year)) + '03010000', '%Y%m%d%H%M')
    num = (nowDatetime - startDatetime).days + 1  # 期号

    # 获取上午和下午的状态码
    statusAm = statusCode(cloudAm, totalAreaAm, highAreaAm, midAreaAm, lowAreaAm)
    statusPm = statusCode(cloudPm, totalAreaPm, highAreaPm, midAreaPm, lowAreaPm)
    statusWholeDay = str(statusAm) + '-' + str(statusPm)

    # 专题图路径
    amTimeStr = os.path.basename(ensureDirAm)
    pmTimeStr = os.path.basename(ensureDirPm)
    # 图1
    if totalAreaAm > 0:
        pictureAm01 = os.path.join(ensureDirAm, '太湖蓝藻水华分布1-%s.jpg' % amTimeStr)
    else:
        pictureAm01 = os.path.join(ensureDirAm, '太湖蓝藻水华分布1-%sPoint.jpg' % amTimeStr)
    if totalAreaPm > 0:
        picturePm01 = os.path.join(ensureDirPm, '太湖蓝藻水华分布1-%s.jpg' % pmTimeStr)
    else:
        picturePm01 = os.path.join(ensureDirPm, '太湖蓝藻水华分布1-%sPoint.jpg' % pmTimeStr)
    pictureAm02 = os.path.join(ensureDirAm, '太湖蓝藻水华分布2-%sPoint.jpg' % amTimeStr)
    pictureAm03 = os.path.join(ensureDirAm, '太湖蓝藻水华分布3-%sPoint.jpg' % amTimeStr)
    picturePm02 = os.path.join(ensureDirPm, '太湖蓝藻水华分布2-%sPoint.jpg' % pmTimeStr)
    picturePm03 = os.path.join(ensureDirPm, '太湖蓝藻水华分布3-%sPoint.jpg' % pmTimeStr)

    # 文字描述================================================================== #
    if statusWholeDay == '1-1':
        description = '%s月%s日，卫星遥感影像显示，上、下午太湖全部被云层覆盖（图1、2），无法判断蓝藻聚集情况。' \
                      % (month, day)
    elif statusWholeDay == '1-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖部分被云层覆盖（图2），' \
                      '无云区域内未发现蓝藻聚集现象。' % (month, day)
    elif statusWholeDay == '1-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖未发现蓝藻聚集现象（图2）。'\
                      % (month, day)
    elif statusWholeDay == '1-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖部分湖区被云层覆盖，' \
                      '无云区域内发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '1-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖发现蓝藻聚集面积约%d平方千米' \
                      '（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '1-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖发现蓝藻聚集面积约%d平方千米' \
                      '（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s，' \
                      '高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '1-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖发现蓝藻聚集面积约%d平方千米' \
                      '（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s，' \
                      '无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '1-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖发现蓝藻聚集面积约%d平方千米' \
                      '（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s，' \
                      '全部为低聚集区（表1、图4）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '1-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖部分湖区被云层覆盖，无云区域内' \
                      '发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的' \
                      '%.1f%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图4），占蓝藻总聚集面积的' \
                      '%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方' \
                      '千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '1-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖部分湖区被云层覆盖，无云区域内' \
                      '发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的' \
                      '%.1f%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图4），占蓝藻总聚集面积的' \
                      '%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '1-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖（图1），无法判断蓝藻聚集情况；下午太湖部分湖区被云层覆盖，无云区域内' \
                      '发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的' \
                      '%.1f%%。下午蓝藻主要分布在%s，全部为低聚集区（表1、图4）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方' \
                      '千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '2-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖全部被云层覆盖（图2），' \
                      '无法判断蓝藻聚集情况。' % (month, day)
    elif statusWholeDay == '2-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖部分被云层覆盖（图2），' \
                      '无云区域内未发现蓝藻聚集现象。' % (month, day)
    elif statusWholeDay == '2-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖未发现蓝藻聚集现象' \
                      '（图2）。' % (month, day)
    elif statusWholeDay == '2-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖部分湖区被云层覆盖，' \
                      '无云区域内发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖' \
                      '总面积的%.1f%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州' \
                      '水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '2-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖发现蓝藻聚集面积约%d' \
                      '平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要' \
                      '分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '2-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖发现蓝藻聚集面积约%d' \
                      '平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要' \
                      '分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '2-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖发现蓝藻聚集面积约%d' \
                      '平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要' \
                      '分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边' \
                      '界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '2-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖发现蓝藻聚集面积约%d' \
                      '平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要' \
                      '分布在%s，全部为低聚集区（表1、图4）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州' \
                      '水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '2-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖部分湖区被云层覆盖，' \
                      '无云区域内发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖' \
                      '总面积的%.1f%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图4），占蓝藻总聚集面积' \
                      '的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方' \
                      '千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '2-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖部分湖区被云层覆盖，' \
                      '无云区域内发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖' \
                      '总面积的%.1f%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图4），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '2-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖（图1），无云区域内未发现蓝藻聚集现象；下午太湖部分湖区被云层覆盖，' \
                      '无云区域内发现蓝藻聚集面积约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖' \
                      '总面积的%.1f%%。下午蓝藻主要分布在%s，全部为低聚集区（表1、图4）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州' \
                      '水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '3-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖全部被云层覆盖（图2），无法判断蓝藻聚集情况。' \
                      % (month, day)
    elif statusWholeDay == '3-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖部分被云层覆盖（图2），无云区域内未发现蓝藻聚集' \
                      '现象。' % (month, day)
    elif statusWholeDay == '3-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖未发现蓝藻聚集现象（图2）。' \
                      % (month, day)
    elif statusWholeDay == '3-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积' \
                      '约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻' \
                      '主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '3-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖发现蓝藻聚集面积约%d平方千米（图2、3），占全湖' \
                      '总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '3-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖发现蓝藻聚集面积约%d平方千米（图2、3），占全湖' \
                      '总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s，高、中、低聚集区' \
                      '面积分别约为%d、%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '3-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖发现蓝藻聚集面积约%d平方千米（图2、3），占全湖' \
                      '总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s，无高聚集区，中、' \
                      '低聚集区面积分别约为%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '3-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖发现蓝藻聚集面积约%d平方千米（图2、3），占全湖' \
                      '总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻主要分布在%s，全部为低聚集区' \
                      '（表1、图4）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '3-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积' \
                      '约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻' \
                      '主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '3-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积' \
                      '约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻' \
                      '主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图4），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '3-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象（图1）；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积' \
                      '约%d平方千米（图2、3），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。下午蓝藻' \
                      '主要分布在%s，全部为低聚集区（表1、图4）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, totalPercentMean, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖全部被云层覆盖（图3），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '4-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分被云层覆盖（图3），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖' \
                      '总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州' \
                      '水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '4-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖未发现蓝藻聚集现象（图3），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻' \
                      '主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '4-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图5），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图5），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表1、图5）；按行政边界划分，无锡水域%d平方千米，' \
                      '占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，' \
                      '上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，' \
                      '占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约' \
                      '为%d、%d、%d平方千米（表1、图5），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，' \
                      '占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，' \
                      '上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，' \
                      '占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积' \
                      '分别约为%d、%d平方千米（表1、图5），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '4-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，' \
                      '上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，' \
                      '占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表1、图5）；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖全部被云层' \
                      '覆盖（图3），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '5-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分被云层' \
                      '覆盖（图3），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要' \
                      '分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '5-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖未发现蓝藻' \
                      '聚集现象（图3），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '5-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区被' \
                      '云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻聚' \
                      '集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图5），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图5），占蓝藻总聚集面积的' \
                      '%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表1、图5）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方' \
                      '千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图5），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米' \
                      '（表1、图5），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '5-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图3、4），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表1、图4）；按行政边界划分，无锡水域%d平方' \
                      '千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '6-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖全部被' \
                      '云层覆盖（图4），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布' \
                      '在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '6-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分被' \
                      '云层覆盖（图4），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻' \
                      '主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '6-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖未发现' \
                      '蓝藻聚集现象（图4），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集' \
                      '区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '6-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '6-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、' \
                      '%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      '下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '6-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、' \
                      '%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      '下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%、' \
                      '%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '6-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、' \
                      '%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      '下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '6-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、' \
                      '%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      '下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '6-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻' \
                      '总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '6-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻' \
                      '总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州' \
                      '水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻' \
                      '总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方' \
                      '千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm,
                         szAreaPm, szPercentPm)
    elif statusWholeDay == '6-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区被' \
                      '云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d' \
                      '平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州' \
                      '水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖全部被云层' \
                      '覆盖（图4），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，' \
                      '无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm,
                         szAreaAm, szPercentAm)
    elif statusWholeDay == '7-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分被云层' \
                      '覆盖（图4），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要' \
                      '分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边' \
                      '界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm,
                         szAreaAm, szPercentAm)
    elif statusWholeDay == '7-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖未发现蓝藻' \
                      '聚集现象（图4），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低' \
                      '聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm,
                         szAreaAm, szPercentAm)
    elif statusWholeDay == '7-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域' \
                      '%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      '下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布' \
                      '在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, highAreaPm, midAreaPm,
                         lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布' \
                      '在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, midAreaPm,
                         lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布' \
                      '在%s，全部为低聚集区（表2、图6）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, highAreaPm, midAreaPm,
                         lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, midAreaPm,
                         lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '7-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖全部被' \
                      '云层覆盖（图4），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布' \
                      '在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '8-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分被云层' \
                      '覆盖（图4），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要' \
                      '分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '8-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖未发现蓝藻' \
                      '聚集现象（图4），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区' \
                      '（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '8-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），' \
                      '蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖发现蓝藻' \
                      '聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布%s，' \
                      '高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，' \
                      '占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积' \
                      '分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '8-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的%.1f%%；下午太湖部分湖区' \
                      '被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方' \
                      '千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，' \
                      '占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖全部被云层覆盖（图4），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、' \
                      '%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '9-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分被云层覆盖（图4），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总' \
                      '面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的' \
                      '%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '9-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖未发现蓝藻聚集现象（图4），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要' \
                      '分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '9-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下' \
                      '午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方' \
                      '千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d' \
                      '平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州' \
                      '水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d' \
                      '平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州' \
                      '水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d' \
                      '平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积' \
                      '的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d' \
                      '平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表1、图3），占蓝藻总聚集' \
                      '面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d' \
                      '平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方' \
                      '千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界' \
                      '划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米' \
                      '（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         midAreaPm, lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm,
                         wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '9-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米' \
                      '（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '全部为低聚集区（表2、图6）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，' \
                      '占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, highAreaAm, midAreaAm, lowAreaAm, highPercentAm, midPercentAm,
                         lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm,
                         wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖全部被云层覆盖（图4），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的' \
                      '%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的' \
                      '%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm,
                         szAreaAm, szPercentAm)
    elif statusWholeDay == '10-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分被云层覆盖（图4），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总' \
                      '面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的' \
                      '%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm,
                         szAreaAm, szPercentAm)
    elif statusWholeDay == '10-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖未发现蓝藻聚集现象（图4），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要' \
                      '分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政' \
                      '边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm,
                         szAreaAm, szPercentAm)
    elif statusWholeDay == '10-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d' \
                      '平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方' \
                      '千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域' \
                      '%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总' \
                      '聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千' \
                      '米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d' \
                      '平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总' \
                      '聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千' \
                      '米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、' \
                      '%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, highAreaPm, midAreaPm,
                         lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总' \
                      '聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千' \
                      '米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集面积的' \
                      '%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, midAreaPm,
                         lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表1、图3），占蓝藻总' \
                      '聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千' \
                      '米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d' \
                      '平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平' \
                      '方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），' \
                      '占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, highAreaPm, midAreaPm,
                         lowAreaPm, highPercentPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d' \
                      '平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方' \
                      '千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d平方千米' \
                      '（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，' \
                      '占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, midAreaPm,
                         lowAreaPm, midPercentPm, lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm,
                         czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '10-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积的' \
                      '%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，无高聚集区，中、低聚集区面积分别约为%d、%d' \
                      '平方千米（表1、图3），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方' \
                      '千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，全部为低聚集区（表2、图6）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, midAreaAm, lowAreaAm, midPercentAm, lowPercentAm, wxAreaAm,
                         wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm, regionStrPm, wxAreaPm, wxPercentPm,
                         czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-1':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖全部被云层覆盖（图4），无法判断蓝藻聚集情况，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                      '上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占' \
                      '%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '11-2':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分被云层覆盖（图4），无云区域内未发现蓝藻聚集现象，上、下午蓝藻平均聚集面积约%d平方千米，占全湖总' \
                      '面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域' \
                      '%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '11-3':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖未发现蓝藻聚集现象（图4），上、下午蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要' \
                      '分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水' \
                      '域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, totalPercentMean, regionStrAm,
                         wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm, szPercentAm)
    elif statusWholeDay == '11-4':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-5':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，无锡水域%d平方千米，占%d%%；' \
                      '常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-6':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-7':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-8':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午蓝藻平均聚集面积约%d平方千米，' \
                      '占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '全部为低聚集区（表2、图6）。按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-9':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；' \
                      '按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      '下午蓝藻主要分布在%s，高、中、低聚集区面积分别约为%d、%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%、' \
                      '%.1f%%；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, highAreaPm, midAreaPm, lowAreaPm, highPercentPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-10':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '无高聚集区，中、低聚集区面积分别约为%d、%d平方千米（表2、图6），占蓝藻总聚集面积的%.1f%%、%.1f%%；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, midAreaPm, lowAreaPm, midPercentPm,
                         lowPercentPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    elif statusWholeDay == '11-11':
        description = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图1、2），占全湖总面积' \
                      '的%.1f%%；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米（图4、5），占全湖总面积的%.1f%%，上、下午' \
                      '蓝藻平均聚集面积约%d平方千米，占全湖总面积的%.1f%%。上午蓝藻主要分布在%s，全部为低聚集区（表1、图3）；按行政边界划分，' \
                      '无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；苏州水域%d平方千米，占%d%%。下午蓝藻主要分布在%s，' \
                      '全部为低聚集区（表2、图6）；按行政边界划分，无锡水域%d平方千米，占%d%%；常州水域%d平方千米，占%d%%；' \
                      '苏州水域%d平方千米，占%d%%。' \
                      % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                         totalPercentMean, regionStrAm, wxAreaAm, wxPercentAm, czAreaAm, czPercentAm, szAreaAm,
                         szPercentAm, regionStrPm, wxAreaPm, wxPercentPm, czAreaPm, czPercentPm, szAreaPm, szPercentPm)
    else:
        description = ''

    # 图片和标签==============================================================
    templateCode = getTemplateCode(statusAm, statusPm)
    labelDict = {}
    pictureDict = {}
    if templateCode == 1:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': picturePm01}
    elif templateCode == 2:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day),
                     'label3': '%s年%s月%s日下午太湖蓝藻遥感监测' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': picturePm01,
                       'template_picture3.jpg': picturePm02}
    elif templateCode == 3:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day),
                     'label3': '%s年%s月%s日下午太湖蓝藻遥感监测' % (year, month, day),
                     'label4': '%s年%s月%s日下午太湖蓝藻聚集强度分级' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': picturePm01,
                       'template_picture3.jpg': picturePm02,
                       'template_picture4.jpg': picturePm03}
    elif templateCode == 4:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日上午太湖蓝藻遥感监测' % (year, month, day),
                     'label3': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': pictureAm02,
                       'template_picture3.jpg': picturePm01}
    elif templateCode == 5:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日上午太湖蓝藻遥感监测' % (year, month, day),
                     'label3': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day),
                     'label4': '%s年%s月%s日下午太湖蓝藻遥感监测' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': pictureAm02,
                       'template_picture3.jpg': picturePm01,
                       'template_picture4.jpg': picturePm02}
    elif templateCode == 6:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日上午太湖蓝藻遥感监测' % (year, month, day),
                     'label3': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day),
                     'label4': '%s年%s月%s日下午太湖蓝藻遥感监测' % (year, month, day),
                     'label5': '%s年%s月%s日下午太湖蓝藻聚集强度分级' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': pictureAm02,
                       'template_picture3.jpg': picturePm01,
                       'template_picture4.jpg': picturePm02,
                       'template_picture5.jpg': picturePm03}
    elif templateCode == 7:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日上午太湖蓝藻遥感监测' % (year, month, day),
                     'label3': '%s年%s月%s日上午太湖蓝藻聚集强度分级' % (year, month, day),
                     'label4': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': pictureAm02,
                       'template_picture3.jpg': pictureAm03,
                       'template_picture4.jpg': picturePm01}
    elif templateCode == 8:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日上午太湖蓝藻遥感监测' % (year, month, day),
                     'label3': '%s年%s月%s日上午太湖蓝藻聚集强度分级' % (year, month, day),
                     'label4': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day),
                     'label5': '%s年%s月%s日下午太湖蓝藻遥感监测' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': pictureAm02,
                       'template_picture3.jpg': pictureAm03,
                       'template_picture4.jpg': picturePm01,
                       'template_picture5.jpg': picturePm02}
    elif templateCode == 9:
        labelDict = {'label1': '%s年%s月%s日上午太湖区域卫星遥感影像' % (year, month, day),
                     'label2': '%s年%s月%s日上午太湖蓝藻遥感监测' % (year, month, day),
                     'label3': '%s年%s月%s日上午太湖蓝藻聚集强度分级' % (year, month, day),
                     'label4': '%s年%s月%s日下午太湖区域卫星遥感影像' % (year, month, day),
                     'label5': '%s年%s月%s日下午太湖蓝藻遥感监测' % (year, month, day),
                     'label6': '%s年%s月%s日下午太湖蓝藻聚集强度分级' % (year, month, day)}
        pictureDict = {'template_picture1.jpg': pictureAm01,
                       'template_picture2.jpg': pictureAm02,
                       'template_picture3.jpg': pictureAm03,
                       'template_picture4.jpg': picturePm01,
                       'template_picture5.jpg': picturePm02,
                       'template_picture6.jpg': picturePm03}
    else:
        pass

    # 生成word文件====================================================
    # 1.生成日报
    replaceText = {'year': year, 'num': num, 'month': month, 'day': day, 'description': description,
                   'highAreaAm': highAreaAm, 'midAreaAm': midAreaAm, 'lowAreaAm': lowAreaAm,
                   'totalAreaAm': totalAreaAm, 'highPercentAm': highPercentAm, 'midPercentAm': midPercentAm,
                   'lowPercentAm': lowPercentAm, 'highAreaPm': highAreaPm, 'midAreaPm': midAreaPm,
                   'lowAreaPm': lowAreaPm, 'totalAreaPm': totalAreaAm, 'highPercentPm': highPercentPm,
                   'midPercentPm': midPercentPm, 'lowPercentPm': lowPercentPm}
    for key in labelDict.keys():
        replaceText[key] = labelDict[key]

    dependDir = globalCfg['depend_path']
    templateDir = os.path.join(dependDir, 'word')
    templatePath = os.path.join(templateDir, 'report_whole_day' + str(templateCode) + '.docx')
    tpl = DocxTemplate(templatePath)
    tpl.render(replaceText)

    replacePic = pictureDict
    for key in replacePic.keys():
        tpl.replace_pic(key, replacePic[key])

    outWordName = '太湖蓝藻水华监测日报-%s.docx' % issue[0:8]
    outWordPath = os.path.join(ensureDirPm, outWordName)
    if os.path.exists(outWordPath):
        os.remove(outWordPath)
    tpl.save(outWordPath)

    # 生成txt文件====================================================
    outTxTName = '太湖蓝藻水华监测日报-%s.txt' % issue[0:8]
    outTxtPath = os.path.join(ensureDirPm, outTxTName)
    if os.path.exists(outTxtPath):
        os.remove(outTxtPath)
    repContext = ['（图1）', '（图2）', '（图3）', '（图4）', '（图1、2）', '（图2、3）', '（图3、4）', '（图4、5）',
                  '（表1、图3）', '（表1、图4）', '（表1、图5）', '（表2、图6）']
    # txt文字第一段
    txtDescription01 = description
    for each in repContext:
        txtDescription01 = txtDescription01.replace(each, '')

    # txt文字第二段
    # 获取上午和下午的状态码
    statusAmTxt = statusCodeTxt(cloudAm, totalAreaAm)
    statusPmTxt = statusCodeTxt(cloudPm, totalAreaPm)
    statusWholeDayTxt = str(statusAmTxt) + '-' + str(statusPmTxt)
    # 查询去年当天情况
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )
    cursor = conn.cursor()

    cloudAm_last = None         # 去年当天上午云量
    cloudPm_last = None         # 去年当天下午云量
    totalAreaAm_last = None     # 去年当天上午面积
    totalAreaPm_last = None     # 去年当天下午面积
    totalArea_last = 0          # 去年当天上下午总面积
    totalArea_count = 0         # 去年当天上下午计次

    # 查询去年当天上午数据
    sqlStr = 'SELECT area,cloud FROM ' + globalCfg['database_table_report_taihu_info'] + \
             ' WHERE date BETWEEN %s AND %s;'
    lastYear = str(int(year) - 1)
    startTime = '%s-%s-%s 00:00:01' % (lastYear, month, day)
    endTime = '%s-%s-%s 11:59:59' % (lastYear, month, day)
    sqlData = (startTime, endTime)
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        totalAreaAm_last = sqlRes[0][0]
        cloudAm_last = sqlRes[0][1]
    if totalAreaAm_last is None:
        amInfo_last = '上午未知'
    else:
        if totalAreaAm_last > 0:
            amInfo_last = '上午面积%d' % totalAreaAm_last
            totalArea_last += totalAreaAm_last
            totalArea_count += 1
        else:
            if cloudAm_last >= 95:
                amInfo_last = '上午全云'
            elif 5 < cloudAm_last < 95:
                amInfo_last = '上午有云无藻'
            else:
                amInfo_last = '上午无云无藻'

    # 查询去年当天下午数据
    sqlStr = 'SELECT area,cloud FROM ' + globalCfg['database_table_report_taihu_info'] + \
             ' WHERE date BETWEEN %s AND %s;'
    lastYear = str(int(year) - 1)
    startTime = '%s-%s-%s 12:00:01' % (lastYear, month, day)
    endTime = '%s-%s-%s 23:59:59' % (lastYear, month, day)
    sqlData = (startTime, endTime)
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        totalAreaPm_last = sqlRes[0][0]
        cloudPm_last = sqlRes[0][1]
    if totalAreaPm_last is None:
        pmInfo_last = '下午未知'
    else:
        if totalAreaPm_last > 0:
            pmInfo_last = '下午面积%d' % totalAreaPm_last
            totalArea_last += totalAreaPm_last
            totalArea_count += 1
        else:
            if cloudPm_last >= 95:
                pmInfo_last = '下午全云'
            elif 5 < cloudPm_last < 95:
                pmInfo_last = '下午有云无藻'
            else:
                pmInfo_last = '下午无云无藻'

    if totalArea_count == 0:
        percentInfo_last = '平均面积0'
    else:
        tempInt = roundCustom(totalArea_last / totalArea_count)
        percentInfo_last = '平均面积%d' % tempInt

    cursor.close()
    conn.close()
    lastInfoStr = '(%s, %s, %s)' % (amInfo_last, pmInfo_last, percentInfo_last)

    if statusWholeDayTxt == '1-1':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上、下午太湖全部被云层覆盖，无法判断蓝藻聚集情况。%s' \
                           '（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '1-2':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖，无法判断蓝藻聚集情况；下午太湖部分被云层覆盖，' \
                           '无云区域内未发现蓝藻聚集现象。%s（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '1-3':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖，无法判断蓝藻聚集情况；下午太湖未发现蓝藻聚集现象。' \
                           '%s（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '1-4':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖，无法判断蓝藻聚集情况；下午太湖部分湖区被云层覆盖，' \
                           '无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s' \
                           '（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '1-5':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖全部被云层覆盖，无法判断蓝藻聚集情况；下午太湖发现蓝藻聚集面积约%d平方千米，' \
                           '占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，' \
                           '占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '2-1':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖，无云区域内未发现蓝藻聚集现象；下午太湖全部被云层覆盖，' \
                           '无法判断蓝藻聚集情况。%s（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '2-2':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖，无云区域内未发现蓝藻聚集现象；下午太湖部分被云层覆盖，' \
                           '无云区域内未发现蓝藻聚集现象。%s（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '2-3':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖，无云区域内未发现蓝藻聚集现象；下午太湖未发现蓝藻聚集现象。' \
                           '%s（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '2-4':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖，无云区域内未发现蓝藻聚集现象；下午太湖部分湖区被云层覆盖，' \
                           '无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s' \
                           '（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '2-5':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分被云层覆盖，无云区域内未发现蓝藻聚集现象；下午太湖发现蓝藻聚集面积约%d' \
                           '平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，' \
                           '占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '3-1':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象；下午太湖全部被云层覆盖，无法判断蓝藻聚集情况。%s' \
                           '（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '3-2':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象；下午太湖部分被云层覆盖，无云区域内未发现蓝藻聚集现象。%s' \
                           '（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '3-3':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象；下午太湖未发现蓝藻聚集现象。%s' \
                           '（注：括号内为去年同期情况，下同）。' % (month, day, lastInfoStr)
    elif statusWholeDayTxt == '3-4':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象；下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d' \
                           '平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，' \
                           '占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '3-5':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖未发现蓝藻聚集现象；下午太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%。' \
                           '上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaPm, totalPercentPm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '4-1':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；' \
                           '下午太湖全部被云层覆盖，无法判断蓝藻聚集情况。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，' \
                           '占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '4-2':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；' \
                           '下午太湖部分被云层覆盖，无云区域内未发现蓝藻聚集现象。上、下午蓝藻平均聚集面积约%d%s' \
                           '（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '4-3':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；' \
                           '下午太湖未发现蓝藻聚集现象。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，' \
                           '占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '4-4':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；' \
                           '下午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集' \
                           '面积约%d%s（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                              lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '4-5':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖部分湖区被云层覆盖，无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；' \
                           '下午太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s' \
                           '（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                              lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '5-1':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；下午太湖全部被云层覆盖，' \
                           '无法判断蓝藻聚集情况。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '5-2':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；下午太湖部分被云层覆盖，' \
                           '无云区域内未发现蓝藻聚集现象。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，' \
                           '占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '5-3':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；下午太湖未发现蓝藻聚集现象。' \
                           '上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaMean, lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '5-4':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；下午太湖部分湖区被云层覆盖，' \
                           '无云区域内发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s' \
                           '（注：括号内为去年同期情况，下同）平方千米，占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                              lastInfoStr, totalPercentMean)
    elif statusWholeDayTxt == '5-5':
        txtDescription02 = '%s月%s日，卫星遥感影像显示，上午太湖发现蓝藻聚集面积约%d平方千米，占全湖总面积的%.1f%%；下午太湖发现蓝藻聚集' \
                           '面积约%d平方千米，占全湖总面积的%.1f%%。上、下午蓝藻平均聚集面积约%d%s（注：括号内为去年同期情况，下同）平方千米，' \
                           '占全湖总面积的%.1f%%。' \
                           % (month, day, totalAreaAm, totalPercentAm, totalAreaPm, totalPercentPm, totalAreaMean,
                              lastInfoStr, totalPercentMean)
    else:
        txtDescription02 = ''

    # txt文字第三段
    search_start1 = '%s-03-01 00:00:01' % (issue[0:4])
    search_end1 = '%s-%s-%s 23:59:59' % (issue[0:4], issue[4:6], issue[6:8])
    search_start2 = '%s-03-01 00:00:01' % (str(int(issue[0:4])-1))
    search_end2 = '%s-%s-%s 23:59:59' % (str(int(issue[0:4])-1), issue[4:6], issue[6:8])
    # [count, mean_area, max_area, max_area_date]
    res1 = searchDate(search_start1, search_end1)
    res2 = searchDate(search_start2, search_end2)

    count_compare = res1[0] - res2[0]
    if count_compare >= 0:
        count_compare_str = '增加%d次' % abs(count_compare)
    else:
        count_compare_str = '减少%d次' % abs(count_compare)
    if res2[1] == 0:
        mean_area_compare_str = '增加0%'
    else:
        mean_area_compare = (res1[1] - res2[1]) / res2[1] * 100
        if mean_area_compare >= 0:
            mean_area_compare_str = '增加%.1f%%' % abs(mean_area_compare)
        else:
            mean_area_compare_str = '减少%.1f%%' % abs(mean_area_compare)
    if res2[2] == 0:
        max_area_compare_str = '增加0%'
    else:
        max_area_compare = (res1[2] - res2[2]) / res2[2] * 100
        if max_area_compare >= 0:
            max_area_compare_str = '增加%.1f%%' % abs(max_area_compare)
        else:
            max_area_compare_str = '减少%.1f%%' % abs(max_area_compare)
    txtDescription03 = '今年3月1日太湖安全度夏应急防控启动以来（截至%s月%s日），太湖蓝藻水华发现%d次，' \
                       '同比%s，平均聚集面积%d平方千米/次，同比%s，最大面积出现于%s，面积为%d平方千米，' \
                       '同比（%s年%s，%s平方千米）%s。' \
                       % (month, day, res1[0], count_compare_str, res1[1], mean_area_compare_str, res1[3], res1[2],
                          str(int(year)-1), res2[3], res2[2], max_area_compare_str)

    with open(outTxtPath, 'w') as txt_f:
        txt_f.write(txtDescription01)
        txt_f.write('\n')
        txt_f.write(txtDescription02)
        txt_f.write('\n')
        txt_f.write(txtDescription03)
        txt_f.write('\n')
    return outWordPath, outTxtPath


if __name__ == '__main__':
    pass