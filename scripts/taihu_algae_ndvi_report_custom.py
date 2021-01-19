# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import datetime

import pymysql
import xlwt
import numpy as np



globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def dayarea(startyear, endyear, startday, endday):
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )
    cursor = conn.cursor()

    yearList = list(range(int(startyear), int(endyear) + 1))
    sqlList = []
    sqlDic = {}
    for year in yearList:
        sDate = '%s-%s 00:00:01' % (year, startday)
        eDate = '%s-%s 23:59:59' % (year, endday)
        sqlStr = "select date,area from t_water_taihu_modis where date between '%s' and '%s' and area>0;" % (
        sDate, eDate)
        cursor.execute(sqlStr)  # 执行
        sqlRes = cursor.fetchall()
        sqlRes1 = list(sqlRes)
        for each in sqlRes1:
            sqlList.append(each)
        sqlDic[year] = sqlRes1

    time_List = []
    max_List = []
    mean_List = []
    for key in sqlDic:
        subkey = [key]
        subdict = dict([(key, sqlDic[key]) for key in subkey])
        for value in subdict.values():
            dicList = []
            for each in value:
                dicList.append(each[1])
            time_List.append(len(dicList))
            max_List.append(max((dicList), default=0))
            cal_mean = np.mean(dicList)
            if np.isnan(cal_mean):
                cal_mean = 0
            mean_List.append(round(cal_mean))

    mean_2=mean_List[-2]
    mean_1=mean_List[-1]
    mean_ratio=str(round(((mean_1-mean_2)/mean_2)*100,1))+'%'
    time_1=time_List[-1]
    time_2=time_List[-2]
    time_ratio=time_1-time_2
    max_1=max_List[-1]
    max_2=max_List[-2]
    max_ratio=str(round(((max_1-max_2)/max_2)*100,1))+'%'

    cursor.close()
    conn.close()

    return sqlList, time_List, max_List, mean_List,mean_ratio,max_ratio,time_ratio


def main(arg1, arg2, arg3, arg4):

    sqlList, time_List, max_List, mean_List, mean_ratio, max_ratio, time_ratio = dayarea(arg1, arg2, arg3, arg4)
    # 日期
    startMonth = int(arg3.split('-')[0])
    startDay = int(arg3.split('-')[1])
    endMonth = int(arg4.split('-')[0])
    endDay = int(arg4.split('-')[1])

    startDateTime = datetime.datetime(2000, startMonth, startDay, 0, 0, 0)
    endDateTime = datetime.datetime(2000, endMonth, endDay, 0, 0, 0)
    dateList = []
    for i in range((endDateTime - startDateTime).days + 1):
        currentDateTime = startDateTime + datetime.timedelta(days=i)
        currentMonth = currentDateTime.month
        currentDay = currentDateTime.day
        currentDateStr = '%d月%d日' % (currentMonth, currentDay)
        dateList.append(currentDateStr)
    # print(dateList)
    list1 = list(range(int(arg1), int(arg2) + 1))
    list_str = ['日期']
    for each in list1:
        list_str.append(str(each) + '年')
    # print(list_str)
    time_title = str(startMonth)+'月'+str(startDay)+'日' + "-" + str(endMonth) + "月"+str(endDay)+'日'
    list_sum = [time_title]
    for each in list1:
        list_sum.append(str(each) + '年')
    list_sum.append('同比')
    # print(list_sum)
    sum = ['发生次数', '最大面积', '平均面积']
    # 创建excel
    workbook = xlwt.Workbook(encoding='utf-8')
    worksheet1 = workbook.add_sheet('sheet1', cell_overwrite_ok=True)
    worksheet2 = workbook.add_sheet('sheet2', cell_overwrite_ok=True)
    #设置单元格居中
    style = xlwt.XFStyle()
    al = xlwt.Alignment()
    al.horz = 0x02
    al.vert = 0x01
    style.alignment = al

    # 写行
    for i in range(0, len(list_str)):
        worksheet1.write(0, i, list_str[i],style)
    # 写列
    for i in range(0, len(dateList)):
        worksheet1.write(i + 1, 0, dateList[i],style)

    for each in sqlList:
        year = each[0].year
        month = each[0].month
        day = each[0].day
        year = str(year) + '年'
        date = str(month) + '月' + str(day) + '日'
        area = each[1]
        a = list_str.index(year)
        b = dateList.index(date)
        worksheet1.write(b + 1, a, area,style)

    for i in range(0, len(list_sum)):
        worksheet2.write(0, i, list_sum[i],style)
    for i in range(0, len(sum)):
        worksheet2.write(i + 1, 0, sum[i],style)

    for i in range(0, len(time_List)):
        worksheet2.write(1, i + 1, time_List[i],style)
    for i in range(0, len(max_List)):
        worksheet2.write(2, i + 1, max_List[i],style)
    for i in range(0, len(mean_List)):
        worksheet2.write(3, i + 1, mean_List[i],style)
    worksheet2.write(1, len(list_sum)-1, time_ratio,style)
    worksheet2.write(2,len(list_sum)-1, max_ratio,style)
    worksheet2.write(3, len(list_sum)-1, mean_ratio,style)
  # 输出excel
    outputRootDir = os.path.join(globalCfg['output_path'], 'Statistic')
    timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    outputDir = os.path.join(outputRootDir, timeStamp)
    os.makedirs(outputDir)
    excelName = time_title + '太湖蓝藻遥感监测自定义报告'
    outExcel = os.path.join(outputDir, excelName + '.xls')
    outExcel = outExcel.replace('\\', '/')



    workbook.save(outExcel)


    # 数据库操作
    db_monitor_time = time_title
    db_report_type = '自定义报告'
    db_process_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

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
    sqlData = (excelName, db_monitor_time, db_report_type, db_process_time, outExcel, 0,
               '太湖', 'EOS', 'MODIS', '6ce5de13-da13-11ea-871a-0242ac110003')
    cursor.execute(sqlStr, sqlData)
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    # startYear = '2001'
    # endYear = '2020'
    # startDay = '01-02'
    # endDay = '09-21'

    startYear = sys.argv[1]
    endYear = sys.argv[2]
    startDay = sys.argv[3]
    endDay = sys.argv[4]

    print(startYear)
    print(endYear)
    print(startDay)
    print(endDay)

    main(startYear, endYear, startDay, endDay)




