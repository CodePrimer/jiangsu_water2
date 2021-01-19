# -*- coding: utf-8 -*-
"""历史数据入库"""

import os
import sys
import json
import time
import shutil
import uuid
from decimal import Decimal, ROUND_HALF_UP

import xlrd
import pymysql

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from tools.RasterRander.UniqueValues import UniqueValues
from tools.RasterRander.RgbComposite import RgbComposite

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')

with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)

TILE_LEVEL = '8-13'


def roundCustom(inNum):
    if not isinstance(inNum, str):
        inNum = str(inNum)
    origin_num = Decimal(inNum)
    answer_num = origin_num.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
    return answer_num


def findFile(pushDir):
    orgTifPath = ''
    algaeTifPath = ''
    cloudTifPath = ''
    xlsxFilePath = ''
    docxFilePath = ''
    for dirName in os.listdir(pushDir):
        if dirName.startswith('其他'):
            targetDir = os.path.join(pushDir, dirName)
            if os.path.isdir(targetDir):
                for fileName in os.listdir(targetDir):
                    if fileName.endswith('EXCEL_res.xlsx'):
                        xlsxFilePath = os.path.join(targetDir, fileName)
                        satType = fileName.split('_')[0]
                        if satType == 'TERRA':
                            satellite = 'T'
                        else:
                            satellite = 'A'
                    if fileName.startswith('TH_cloud') and fileName.endswith('.tif'):
                        cloudTifPath = os.path.join(targetDir, fileName)
    for dirName in os.listdir(pushDir):
        if dirName.startswith('卫星中心'):
            targetDir = os.path.join(pushDir, dirName)
            if os.path.isdir(targetDir):
                for fileName in os.listdir(targetDir):
                    if fileName.startswith('TH_MODIS') and fileName.endswith('.tif'):
                        orgTifPath = os.path.join(targetDir, fileName)
                    if fileName.startswith('th') and fileName.endswith('.tif'):
                        algaeTifPath = os.path.join(targetDir, fileName)
                    if fileName.startswith('太湖蓝藻水华监测日报-') and fileName.endswith(satellite+'.doc'):
                        docxFilePath = os.path.join(targetDir, fileName)

    print(orgTifPath)
    print(algaeTifPath)
    print(cloudTifPath)
    print(xlsxFilePath)
    print(docxFilePath)
    return orgTifPath, algaeTifPath, cloudTifPath, xlsxFilePath, docxFilePath


def readExcel(excelPath, issue):
    workbook = xlrd.open_workbook(excelPath)
    table = workbook.sheet_by_index(0)
    lineData = table.row_values(1)
    db_num = str(int(lineData[0]))
    db_date = '%s-%s-%s %s:%s:00' % (issue[0:4], issue[4:6], issue[6:8], issue[8:10], issue[10:12])
    db_threshold = str(lineData[3])
    db_ndvi_max = str(lineData[4])
    db_ndvi_min = str(lineData[5])
    db_ndvi_mean = str(lineData[6])
    db_boundary = str(int(lineData[7]))
    if str(lineData[8]).strip() == '':
        db_area = '0'
    else:
        db_area = str(int(roundCustom(lineData[8])))
    region_name_list = ['竺山湖', '梅梁湖', '贡湖', '西部沿岸', '南部沿岸', '湖心区', '东部沿岸', '东太湖']
    db_region_list = ['0', '0', '0', '0', '0', '0', '0', '0']
    regionStr = lineData[13]
    for i in range(len(region_name_list)):
        if region_name_list[i] in regionStr:
            db_region_list[i] = '1'
    db_region_area = ','.join(db_region_list)
    if str(lineData[10]).strip() == '':
        db_high = '0'
    else:
        db_high = str(int(roundCustom(lineData[10])))
    if str(lineData[11]).strip() == '':
        db_mid = '0'
    else:
        db_mid = str(int(roundCustom(lineData[11])))
    if str(lineData[12]).strip() == '':
        db_low = '0'
    else:
        db_low = str(int(roundCustom(lineData[12])))
    if str(lineData[14]).strip() == '':
        db_cloud = '0'
    else:
        db_cloud = str(int(roundCustom(lineData[14])))
    if str(lineData[16]).strip() == '':
        db_type = ''
    else:
        db_type = str(int(roundCustom(lineData[16])))
    db_grade = str(lineData[20])
    db_is_push = 1
    info = {
        'db_num': db_num,
        'db_date': db_date,
        'db_threshold': db_threshold,
        'db_ndvi_max': db_ndvi_max,
        'db_ndvi_min': db_ndvi_min,
        'db_ndvi_mean': db_ndvi_mean,
        'db_boundary': db_boundary,
        'db_area': db_area,
        'db_region_area': db_region_area,
        'db_high': db_high,
        'db_mid': db_mid,
        'db_low': db_low,
        'db_cloud': db_cloud,
        'db_type': db_type,
        'db_grade': db_grade,
        'db_is_push': db_is_push
    }
    return info


def executeSql1(algaeTifPath, info):

    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )

    # t_export_image
    algaeTifName = os.path.basename(algaeTifPath)
    cursor = conn.cursor()
    image_uuid = str(uuid.uuid4())
    db_path = info['db_path'].replace('\\', '/').replace('/mnt/resource/', '')
    db_lat_lr = 30.85921
    db_lon_lr = 120.724
    db_lon_ul = 119.78622
    db_lat_ul = 31.66442
    db_acquire_time = info['db_date']
    db_cloud = info['db_cloud']
    db_area = info['db_area']
    db_process_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    db_threshold = info['db_threshold']
    db_model_uuid = '6ce5de13-da13-11ea-871a-0242ac110003'
    sqlStr = 'INSERT INTO ' + globalCfg['database_table_export_image'] + \
             ' (uuid,name,path,type,model_type,satellite,sensor,lat_lr,lon_lr,lon_ul,lat_ul,' + \
             'acquire_time,cloud,area,process_time,is_deleted,model_uuid,colorbar_min,colorbar_max,' \
             'colorbar_tick,colorbar_color,unit,is_edit,is_edited,threshold) ' + \
             'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
    sqlData = (image_uuid, algaeTifName, db_path, 'tif', 'algae', info['db_satellite'], 'MODIS', db_lat_lr,
               db_lon_lr, db_lon_ul, db_lat_ul, db_acquire_time, db_cloud, db_area, db_process_time, 0,
               db_model_uuid, '无', '有', '水华', '#ffff00', '', 0, 1, db_threshold)
    cursor.execute(sqlStr, sqlData)
    conn.commit()

    # t_water_taihu_modis
    db_date = info['db_date']
    db_num = info['db_num']
    db_ndvi_max = info['db_ndvi_max']
    db_ndvi_min = info['db_ndvi_min']
    db_ndvi_mean = info['db_ndvi_mean']
    db_boundary = info['db_boundary']
    db_area = info['db_area']
    db_region_area = info['db_region_area']
    db_high = info['db_high']
    db_mid = info['db_mid']
    db_low = info['db_low']
    db_type = info['db_type']
    db_grade = info['db_grade']
    sqlStr = 'INSERT INTO ' + globalCfg['database_table_report_taihu_info'] + \
             ' (number,date,ndvi_threshold,ndvi_max,ndvi_min,ndvi_mean,boundary,area,region_area,high_area,' \
             'mid_area,low_area,cloud,type,ndvi_grade,is_push,image_uuid) ' \
             'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);'
    sqlData = (db_num, db_date, db_threshold, db_ndvi_max, db_ndvi_min, db_ndvi_mean, db_boundary,
               db_area, db_region_area, db_high, db_mid, db_low, db_cloud, db_type,
               db_grade, 1, image_uuid)
    cursor.execute(sqlStr, sqlData)
    conn.commit()


def main(yuanshi_tif, lanzao_tif, yun_tif, excel_file, doc_file):
    modelUuid = '6ce5de13-da13-11ea-871a-0242ac110003'

    # 创建结果文件夹
    outputRootDir = globalCfg['output_path']
    timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    outputDir = os.path.join(outputRootDir, modelUuid, timeStamp)
    os.makedirs(outputDir)

    # 拷贝原始TIF 蓝藻TIF 云TIF到结果文件夹
    satellite = os.path.basename(excel_file).split('_')[0].upper()
    yyyyMMdd = os.path.basename(yuanshi_tif).split('_')[2]
    hhmm = os.path.basename(yuanshi_tif).split('_')[3].replace('.tif', '')
    issue = yyyyMMdd + hhmm
    basename = satellite + '_MODIS_L2_' + issue + '_250_00_00'
    print(basename)

    info = readExcel(excel_file, issue)
    info['db_satellite'] = satellite
    # l2
    l2TifName = basename + '_taihu_algae_ndvi.l2.tif'
    l2TifPath = os.path.join(outputDir, l2TifName)
    shutil.copyfile(yuanshi_tif, l2TifPath)

    # algae
    algaeTifName = basename + '_taihu_algae_ndvi.tif'
    algaeTifPath = os.path.join(outputDir, algaeTifName)
    shutil.copyfile(lanzao_tif, algaeTifPath)
    info['db_path'] = algaeTifPath

    # cloud
    if yun_tif:
        cloudTifName = basename + '_taihu_algae_ndvi.cloud.tif'
        cloudTifPath = os.path.join(outputDir, cloudTifName)
        shutil.copyfile(yun_tif, cloudTifPath)
    else:
        cloudTifPath = ''

    # doc
    if doc_file:
        dailyDocName = basename + '_taihu_algae_ndvi.doc'
        dailyDocPath = os.path.join(outputDir, dailyDocName)
        shutil.copyfile(doc_file, dailyDocPath)

    time.sleep(1)

    # # 切片
    # tileDict = {}
    # # 1.假彩色底图切片 falseColor
    # falseColorTifName = os.path.basename(l2TifPath).replace('.tif', '_false.tif')
    # falseColorTifPath = os.path.join(outputDir, falseColorTifName)
    # RgbComposite.Compose(l2TifPath, [1, 2, 1], noDataValue=0,
    #                      returnMode='GEOTIFF', outputPath=falseColorTifPath,
    #                      stretchType='LinearPercent', stretchParam=[0], isAlpha=True)
    # tileDict['falseColor'] = {'tif': falseColorTifPath, 'name': basename + '_falseColor'}
    #
    # # 2.云产品切片 cloud
    # if cloudTifPath:
    #     cloudRenderTifName = os.path.basename(cloudTifPath).replace('.tif', '_render.tif')
    #     cloudRenderTifPath = os.path.join(outputDir, cloudRenderTifName)
    #     colorTable = {1: (255, 255, 255)}
    #     UniqueValues.Render(cloudTifPath, colorTable, returnMode='GEOTIFF', outputPath=cloudRenderTifPath, isAlpha=True)
    #     tileDict['cloud'] = {'tif': cloudRenderTifPath, 'name': basename+'_cloud', 'legendType': '1',
    #                          'legendColor': [(255, 255, 255)], 'legendName': ['云']}
    #
    # # 3.蓝藻产品切片
    # algaeRenderTifName = os.path.basename(algaeTifPath).replace('.tif', '_render.tif')
    # algaeRenderTifPath = os.path.join(outputDir, algaeRenderTifName)
    # colorTable = {1: (255, 251, 0)}
    # UniqueValues.Render(algaeTifPath, colorTable, returnMode='GEOTIFF', outputPath=algaeRenderTifPath, isAlpha=True)
    # tileDict['taihu_algae_ndvi'] = {'tif': algaeRenderTifPath, 'name': basename + '_taihu_algae_ndvi',
    #                                 'legendType': '1', 'legendColor': [(255, 251, 0)], 'legendName': ['水华']}
    #
    # # 调用gdal2tiles工具进行切片
    # pythonPath = globalCfg['python_path']
    # gdal2tilesPath = globalCfg['gdal2tiles_path']
    # tileOutRootDir = globalCfg['tile_server_path']
    # for key in tileDict.keys():
    #     tileTif = tileDict[key]['tif']
    #     tileOutDir = os.path.join(tileOutRootDir, tileDict[key]['name'])
    #     if os.path.exists(tileOutDir):
    #         shutil.rmtree(tileOutDir)
    #     cmd = '%s %s -z %s -w all %s %s' % (pythonPath, gdal2tilesPath, TILE_LEVEL, tileTif, tileOutDir)
    #     os.system(cmd)
    #     os.remove(tileTif)
    #     tileDict[key]['path'] = tileOutDir

    # # doc转pdf
    # outPdfDir = os.path.join(globalCfg['taihu_report_remote'], issue[0:8])
    # if not os.path.exists(outPdfDir):
    #     os.makedirs(outPdfDir)
    # cmdStr = 'libreoffice6.3 --headless --convert-to pdf:writer_pdf_Export ' + dailyDocPath + ' --outdir ' + outPdfDir
    # print(cmdStr)
    # try:
    #     os.system(cmdStr)
    #     print('Convert PDF Success.')
    # except Exception as e:
    #     print(e)

    executeSql1(algaeTifPath, info)


if __name__ == '__main__':
    # rootDir = r'F:\省中心历史数据\省中心蓝藻监测数据入库--2018年'
    # rootDir = r'F:\省中心历史数据\temp'
    rootDir = sys.argv[1]
    dirList = os.listdir(rootDir)
    i = 0
    for dirName in dirList:
        totalNum = len(dirList)
        strInfo = '%s / %s' % (str(i+1), str(totalNum))
        pushDir = os.path.join(rootDir, dirName)
        yuanshi_tif, lanzao_tif, yun_tif, excel_file, doc_file = findFile(pushDir)
        main(yuanshi_tif, lanzao_tif, yun_tif, excel_file, doc_file)
        print(strInfo)
        i += 1
