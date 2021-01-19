# -*- coding: utf-8 -*-

"""
监测FTP MODIS250m数据
1.下载ftp文件
2.调用MODIS250m预处理
3.调用太湖蓝藻产品生产
"""

import os
import sys
from ftplib import FTP
import time
import pymysql
import uuid
import json

curPath = os.path.abspath(os.path.dirname(__file__))
projDir = os.path.split(curPath)[0]
sys.path.append(projDir)

from preprocess.preprocess_modis250_aqua import aqua_preprocess
from product.taihu_algae_ndvi import call_main as do_product

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def sqlQuery(fileName):
    """查询t_import_image表中是否有当期数据"""
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )
    cursor = conn.cursor()

    sql = 'SELECT * FROM ' + globalCfg['database_table_import_image'] + \
          ' WHERE name=%s AND is_download=1;'
    sql_data = fileName
    cursor.execute(sql, sql_data)
    sql_res = cursor.fetchall()
    cursor.close()
    conn.close()
    if len(sql_res) == 0:
        return False
    else:
        return True


def downloadFtpFile(ftp, ftpFilePath, downloadDir, downloadName):
    """

    :param ftp:
    :param ftpFilePath:
    :param downloadDir:
    :param downloadName:
    :return:
    """
    startTime = time.time()
    ftpFileSize = ftp.size(ftpFilePath)
    downloadFilePath = os.path.join(downloadDir, downloadName)
    fp = open(downloadFilePath, 'wb')
    file_handle = fp.write
    ftp.set_debuglevel(0)
    ftp.retrbinary('RETR %s' % ftpFilePath, file_handle, 1024)
    endTime = time.time()
    downloadFileSize = os.path.getsize(downloadFilePath)

    if downloadFileSize == 0:
        print('%s下载失败')
        fp.close()
        os.remove(downloadFilePath)
        return False
    else:
        print('%s传输完毕，文件大小:%.2fkB, 耗时%f' % (ftpFilePath, downloadFileSize, endTime - startTime))
        fp.close()

        # 下载数据入库
        db_uuid = str(uuid.uuid4())
        db_name = downloadName
        db_path = downloadFilePath
        issue = ''.join(downloadName.split('_')[2:7]) + '00'
        db_acquire_time = '%s-%s-%s %s:%s:%s' % (issue[0:4], issue[4:6], issue[6:8], issue[8:10], issue[10:12], issue[12:14])
        db_is_download = 1

        conn = pymysql.connect(
            db=globalCfg['database'],
            user=globalCfg['database_user'],
            password=globalCfg['database_passwd'],
            host=globalCfg['database_host'],
            port=globalCfg['database_port']
        )
        cursor = conn.cursor()
        sql = 'INSERT INTO ' + globalCfg['database_table_import_image'] + \
              ' (uuid,name,path,acquire_time,is_download)' + \
              ' VALUES (%s,%s,%s,%s,%s);'
        sql_data = (db_uuid, db_name, db_path, db_acquire_time, db_is_download)
        cursor.execute(sql, sql_data)
        conn.commit()
        cursor.close()
        conn.close()
        return True


def main():
    # 连接ftp
    ftpUrl = '192.168.50.75'
    ftp = FTP()
    ftp.connect(ftpUrl)
    ftpUserName = 'puusadmin'
    ftpPassword = 'Stb412@.2020_75'
    ftp.login(ftpUserName, ftpPassword)
    print('Connect FTP %s successful.' % ftpUrl)

    # 可变参数
    satelliteType = 'AQUA'

    # 数据目录
    monStr = '{:0>2d}'.format(time.localtime().tm_mon)
    dayStr = '{:0>2d}'.format(time.localtime().tm_mday)
    pwd = '/PUUSDATA/%s/MODIS/L1/%s/%s/%s' % \
          (satelliteType, time.localtime().tm_year, monStr, dayStr)
    hhmmList = []  # 当日不同小时分钟文件夹列表
    try:
        ftp.cwd(pwd)
        hhmmList = ftp.nlst()
    except:
        print('Cannot Find FTP Dir: %s' % pwd)
        ftp.quit()
    for hhmm in hhmmList:
        hhmmDir = pwd + '/' + hhmm
        ftp.cwd(hhmmDir)
        fileList = ftp.nlst()

        modisFiles = {'MOD02QKM': '', 'MOD03': ''}
        for f in fileList:
            if f[-4:] == '.hdf' and len(f.split('_')) == 9 and f.split('.')[1] == 'MOD02QKM':  # TODO
                if not sqlQuery(f):
                    # 数据库中未查询到记录，进行下载
                    ftpFilePath = hhmmDir + '/' + f
                    downloadDir = os.path.join(globalCfg['ftp_tmp'], 'MODIS')
                    if not os.path.isdir(downloadDir):
                        os.makedirs(downloadDir)
                    print('Start Download %', ftpFilePath)
                    if downloadFtpFile(ftp, ftpFilePath, downloadDir, f):
                        print('Download %s successful.' % ftpFilePath)
                        modisFiles['MOD02QKM'] = os.path.join(downloadDir, f).replace('\\', '/')
                    else:
                        print('Download %s failed!' % ftpFilePath)
            elif f[-4:] == '.hdf' and len(f.split('_')) == 9 and f.split('.')[1] == 'MOD03':
                if not sqlQuery(f):
                    ftpFilePath = hhmmDir + '/' + f
                    downloadDir = os.path.join(globalCfg['ftp_tmp'], 'MODIS')
                    if not os.path.isdir(downloadDir):
                        os.makedirs(downloadDir)
                    print('Start Download %', ftpFilePath)
                    if downloadFtpFile(ftp, ftpFilePath, downloadDir, f):
                        print('Download %s successful.' % ftpFilePath)
                        modisFiles['MOD03'] = os.path.join(downloadDir, f).replace('\\', '/')
                    else:
                        print('Download %s failed!' % ftpFilePath)
            else:
                continue

        if modisFiles['MOD03'] and modisFiles['MOD02QKM']:
            # 调用预处理
            print('start preprocess modis data.')
            issue = ''.join(os.path.basename(modisFiles['MOD03']).split('_')[2:7])
            processOutputName = 'AQUA_MODIS_L2_%s_250_00_00.tif' % issue
            processOutputPath = os.path.join(globalCfg['input_path'], 'satellite', 'EOS-MODIS-250', processOutputName)
            if os.path.exists(processOutputPath):
                os.remove(processOutputPath)
            aqua_preprocess(modisFiles['MOD02QKM'], modisFiles['MOD03'], processOutputPath)

            # 调用产品
            print('start generate algae product.')
            # TODO
            do_product(processOutputPath, '6ce5de13-da13-11ea-871a-0242ac110003')
        else:
            print('Lost Data.Failed!')

    # ftp.quit()


if __name__ == '__main__':

    main()

