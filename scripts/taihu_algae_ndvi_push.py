# -*- coding: utf-8 -*-
"""
    太湖蓝藻编辑页面 推送功能按钮

    1.生成全天报告
    2.生成txt日报
    3.分类存放并压缩
"""

import os
import sys
import json
import shutil
import datetime

import pymysql

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from scripts.taihu_algae_ndvi_report_whole_day import wholeDayReport

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')

with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


ENSURE_ROOT_DIR = globalCfg['taihu_ensurefile']  # 确定按钮生成文件根目录
PUSH_ROOT_DIR = globalCfg['taihu_push_path']  # 推送按钮生成文件根目录


class Push(object):

    def __init__(self, jsonT, jsonA, pushType):
        self.jsonT = jsonT             # 外部传参 上午json文件路径
        self.jsonA = jsonA             # 外部传参 下午json文件路径
        self.pushType = pushType       # 外部传参 推送标识 T上午星 A下午星
        self.pushType2 = ''            # 未推送标识 即除pushType另外一个选项
        self.pushJson = ''             # 被推送的json
        self.pushJson2 = ''            # 未被推送的json
        self.yyyyMMdd = ''             # 年月日标识
        self.pushDir = ''              # 推送结果文件夹路径

        self.ensureDir = ''         # 推送标识期次的确定按钮生成文件夹路径
        self.ensureDir2 = ''        # 未推送标识标识期次的确定按钮生成文件夹路径

        self.fileListQt = []        # 推送其他文件列表
        self.fileListStb = []       # 推送生态部文件列表
        self.fileListWxzx = []      # 推送卫星中心文件列表
        self.fileListWx = []        # 推送无锡站文件列表

    def doInit(self):
        if self.pushType == 'T':
            self.pushType2 = 'A'
            if not self.jsonT:
                return False
            self.jsonT = os.path.join(globalCfg['map_dir'], self.jsonT)
            if self.jsonA:
                self.jsonA = os.path.join(globalCfg['map_dir'], self.jsonA)
            self.yyyyMMdd = os.path.basename(self.jsonT).split('_')[3][0:8]
            self.pushJson = self.jsonT
            self.pushJson2 = self.jsonA
        elif self.pushType == 'A':
            self.pushType2 = 'T'
            if not self.jsonA:
                return False
            self.jsonA = os.path.join(globalCfg['map_dir'], self.jsonA)
            if self.jsonT:
                self.jsonT = os.path.join(globalCfg['map_dir'], self.jsonT)
            self.yyyyMMdd = os.path.basename(self.jsonA).split('_')[3][0:8]
            self.pushJson = self.jsonA
            self.pushJson2 = self.jsonT
        else:
            return False

        ensureDir = os.path.join(ENSURE_ROOT_DIR, self.yyyyMMdd + self.pushType)
        if not os.path.exists(ensureDir):
            return False
        else:
            self.ensureDir = ensureDir

        ensureDir2 = os.path.join(ENSURE_ROOT_DIR, self.yyyyMMdd + self.pushType2)
        if os.path.exists(ensureDir2):
            self.ensureDir2 = ensureDir2

        # 创建推送结果文件夹
        pushDirName = '结果' + self.yyyyMMdd
        self.pushDir = os.path.join(PUSH_ROOT_DIR, pushDirName)
        if os.path.exists(self.pushDir):
            shutil.rmtree(self.pushDir)
        os.makedirs(self.pushDir)
        return True

    def copyQt(self):
        """其他文件夹"""
        for filename in os.listdir(self.ensureDir):
            if filename.endswith('江苏省太湖蓝藻遥感监测日报.docx'):
                self.fileListQt.append(os.path.join(self.ensureDir, filename))
            if filename.endswith('EXCEL_res.xlsx'):
                self.fileListQt.append(os.path.join(self.ensureDir, filename))
            if filename.startswith('TH_Break_'):
                self.fileListQt.append(os.path.join(self.ensureDir, filename))
            if filename.startswith('TH_cloud_'):
                self.fileListQt.append(os.path.join(self.ensureDir, filename))

        # 复制
        copyDir = os.path.join(self.pushDir, '其他' + self.yyyyMMdd)
        if os.path.exists(copyDir):
            shutil.rmtree(copyDir)
        os.makedirs(copyDir)
        for each in self.fileListQt:
            shutil.copyfile(each, os.path.join(copyDir, os.path.basename(each)))

    def copyWx(self):
        """无锡站文件夹"""
        for filename in os.listdir(self.ensureDir):
            if filename.endswith('EXCEL_resWX.xlsx'):
                self.fileListWx.append(os.path.join(self.ensureDir, filename))
            if filename.startswith('TH_MODIS_'):
                self.fileListWx.append(os.path.join(self.ensureDir, filename))

        # 复制
        copyDir = os.path.join(self.pushDir, '无锡站' + self.yyyyMMdd)
        if os.path.exists(copyDir):
            shutil.rmtree(copyDir)
        os.makedirs(copyDir)
        for each in self.fileListWx:
            shutil.copyfile(each, os.path.join(copyDir, os.path.basename(each)))

    def copyWxzx(self):
        """卫星中心文件夹"""
        for filename in os.listdir(self.ensureDir):
            if filename.startswith('太湖蓝藻水华分布1') and filename.endswith('_部卫星中心专用.jpg'):
                self.fileListWxzx.append(os.path.join(self.ensureDir, filename))
            if filename.startswith('太湖蓝藻水华监测日报-') and filename.endswith('.docx'):
                self.fileListWxzx.append(os.path.join(self.ensureDir, filename))
            if filename.startswith('TH_MODIS_'):
                self.fileListWxzx.append(os.path.join(self.ensureDir, filename))
            if filename.startswith('TH_shuihua_'):
                self.fileListWxzx.append(os.path.join(self.ensureDir, filename))

        if self.pushJson2 != '':
            for filename in os.listdir(self.ensureDir2):
                if filename.startswith('TH_shuihua_'):
                    self.fileListWxzx.append(os.path.join(self.ensureDir2, filename))
                if filename.startswith('太湖蓝藻水华监测日报-') and filename.endswith('.docx'):
                    self.fileListWxzx.append(os.path.join(self.ensureDir2, filename))

        # 复制
        copyDir = os.path.join(self.pushDir, '卫星中心' + self.yyyyMMdd)
        if os.path.exists(copyDir):
            shutil.rmtree(copyDir)
        os.makedirs(copyDir)
        for each in self.fileListWxzx:
            shutil.copyfile(each, os.path.join(copyDir, os.path.basename(each)))

    def copyStb(self):
        """生态部文件夹"""

        # 生成全天报告和生态部txt
        if self.ensureDir2 == '':
            for filename in os.listdir(self.ensureDir):
                if filename == '太湖蓝藻水华监测日报-%s%s.docx' % (self.yyyyMMdd, self.pushType):
                    self.fileListStb.append(os.path.join(self.ensureDir, filename))
        else:
            if 'TERRA_MODIS' in self.pushJson:
                jsonPathAm = self.pushJson
                jsonPathPm = self.pushJson2
            else:
                jsonPathAm = self.pushJson2
                jsonPathPm = self.pushJson
            if self.pushType == 'T':
                ensureDirAm = self.ensureDir
                ensureDirPm = self.ensureDir2
            else:
                ensureDirAm = self.ensureDir2
                ensureDirPm = self.ensureDir
            wholeDayReportPath, wholeDayTxtPath = wholeDayReport(jsonPathAm, jsonPathPm, ensureDirAm, ensureDirPm)
            self.fileListStb.append(wholeDayReportPath)
            self.fileListStb.append(wholeDayTxtPath)

        # 推送图片
        with open(self.pushJson, 'r') as f:
            jsonData = json.load(f)
        totalArea = jsonData['totalArea']
        if totalArea == 0:
            for filename in os.listdir(self.ensureDir):
                if filename == '太湖蓝藻水华分布1-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType):
                    self.fileListStb.append(os.path.join(self.ensureDir, filename))
        elif 0 < totalArea < 300:
            for filename in os.listdir(self.ensureDir):
                if filename == '太湖蓝藻水华分布1-%s%s.jpg' % (self.yyyyMMdd, self.pushType):
                    self.fileListStb.append(os.path.join(self.ensureDir, filename))
                if filename == '太湖蓝藻水华分布2-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType):
                    self.fileListStb.append(os.path.join(self.ensureDir, filename))
        else:
            for filename in os.listdir(self.ensureDir):
                if filename == '太湖蓝藻水华分布1-%s%s.jpg' % (self.yyyyMMdd, self.pushType):
                    self.fileListStb.append(os.path.join(self.ensureDir, filename))
                if filename == '太湖蓝藻水华分布2-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType):
                    self.fileListStb.append(os.path.join(self.ensureDir, filename))
                if filename == '太湖蓝藻水华分布3-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType):
                    self.fileListStb.append(os.path.join(self.ensureDir, filename))

        if self.pushJson2 != '':
            with open(self.pushJson2, 'r') as f:
                jsonData = json.load(f)
            totalArea = jsonData['totalArea']
            if totalArea == 0:
                for filename in os.listdir(self.ensureDir2):
                    if filename == '太湖蓝藻水华分布1-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType2):
                        self.fileListStb.append(os.path.join(self.ensureDir2, filename))
            elif 0 < totalArea < 300:
                for filename in os.listdir(self.ensureDir2):
                    if filename == '太湖蓝藻水华分布1-%s%s.jpg' % (self.yyyyMMdd, self.pushType2):
                        self.fileListStb.append(os.path.join(self.ensureDir2, filename))
                    if filename == '太湖蓝藻水华分布2-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType2):
                        self.fileListStb.append(os.path.join(self.ensureDir2, filename))
            else:
                for filename in os.listdir(self.ensureDir2):
                    if filename == '太湖蓝藻水华分布1-%s%s.jpg' % (self.yyyyMMdd, self.pushType2):
                        self.fileListStb.append(os.path.join(self.ensureDir2, filename))
                    if filename == '太湖蓝藻水华分布2-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType2):
                        self.fileListStb.append(os.path.join(self.ensureDir2, filename))
                    if filename == '太湖蓝藻水华分布3-%s%sPoint.jpg' % (self.yyyyMMdd, self.pushType2):
                        self.fileListStb.append(os.path.join(self.ensureDir2, filename))

        # 复制
        copyDir = os.path.join(self.pushDir, '生态部' + self.yyyyMMdd)
        if os.path.exists(copyDir):
            shutil.rmtree(copyDir)
        os.makedirs(copyDir)
        for each in self.fileListStb:
            shutil.copyfile(each, os.path.join(copyDir, os.path.basename(each)))

    def zip(self):
        # 压缩
        zipRootDir = PUSH_ROOT_DIR
        zipFileName = os.path.basename(self.pushDir) + '.zip'
        zipFilePath = os.path.join(zipRootDir, zipFileName)
        if os.path.exists(zipFilePath):
            os.remove(zipFilePath)
        os.system('cd %s && zip -r %s %s' % (zipRootDir, zipFileName, os.path.basename(self.pushDir)))
        print('Zip Successful.')


def executeSql(dateTime, modelUuid):
    dt = datetime.datetime.strptime(dateTime, '%Y%m%d')
    date = dt.strftime('%Y-%m-%d')
    dateStart = date + ' 00:00:01'
    dateMid = date + ' 12:00:00'
    dateEnd = date + ' 23:59:59'

    jsonPathT = ''      # 上午数据的json文件路径
    imageUuidT = ''     # 上午数据的t_export_image中uuid
    jsonPathA = ''      # 下午数据的json文件路径
    imageUuidA = ''     # 下午数据的t_export_image中uuid

    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )
    cursor = conn.cursor()
    # 查找上午数据
    sqlStr = 'SELECT uuid,path FROM ' + globalCfg['database_table_export_image'] + \
             ' WHERE acquire_time BETWEEN %s AND %s AND model_uuid=%s AND is_deleted = 0 ;'
    sqlData = (dateStart, dateMid, modelUuid)
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        imageUuidT = sqlRes[0][0]
        jsonName = os.path.basename(sqlRes[0][1]).replace('.tif', '.json')
        jsonDir = os.path.dirname(sqlRes[0][1])
        jsonPathT = os.path.join(jsonDir, jsonName)
    # 查找下午数据
    sqlStr = 'SELECT uuid,path FROM ' + globalCfg['database_table_export_image'] + \
             ' WHERE acquire_time BETWEEN %s AND %s AND model_uuid=%s AND is_deleted = 0 ;'
    sqlData = (dateMid, dateEnd, modelUuid)
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        imageUuidA = sqlRes[0][0]
        jsonName = os.path.basename(sqlRes[0][1]).replace('.tif', '.json')
        jsonDir = os.path.dirname(sqlRes[0][1])
        jsonPathA = os.path.join(jsonDir, jsonName)
    cursor.close()
    conn.close()

    return jsonPathT, jsonPathA, imageUuidT, imageUuidA


def main(jsonPathT, jsonPathA, pushType, imageUuidT, imageUuidA):

    pushObj = Push(jsonPathT, jsonPathA, pushType)
    flag = pushObj.doInit()
    if not flag:
        print('Push script ERROR!')
        return

    pushObj.copyQt()
    pushObj.copyWx()
    pushObj.copyWxzx()
    pushObj.copyStb()
    pushObj.zip()

    # 数据库更新，添加推送字段
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )
    cursor = conn.cursor()
    if pushType == 'T':
        sqlUuid = imageUuidT        # 该uuid的is_push改为1
        sqlUuid2 = imageUuidA       # 该uuid的is_push改为2
    elif pushType == 'A':
        sqlUuid = imageUuidA
        sqlUuid2 = imageUuidT
    else:
        sqlUuid = ''
        sqlUuid2 = ''

    # 将推送的记录is_push更新为1
    if sqlUuid:
        sqlStr = 'UPDATE ' + globalCfg['database_table_report_taihu_info'] + \
                 ' SET is_push=1 where image_uuid=%s;'
        cursor.execute(sqlStr, sqlUuid)
        conn.commit()

    # 将未推送的记录is_push更新为0
    if sqlUuid2:
        sqlStr = 'UPDATE ' + globalCfg['database_table_report_taihu_info'] + \
                 ' SET is_push=0 where image_uuid=%s;'
        cursor.execute(sqlStr, sqlUuid2)
        conn.commit()

    cursor.close()
    conn.close()


if __name__ == '__main__':

    # 传参信息
    # dateTime 推送页面的产品期次时间 yyyy-MM-dd HH:mm:ss
    # pushType 选择的推送类型 T代表上午星 A代表下午星

    # dateTime = '20201230'
    # pushType = 'T'

    dateTime = sys.argv[1]
    pushType = sys.argv[2]

    modelUuid = '6ce5de13-da13-11ea-871a-0242ac110003'      # 前端未传参，写死

    jsonPathT, jsonPathA, imageUuidT, imageUuidA = executeSql(dateTime, modelUuid)

    main(jsonPathT, jsonPathA, pushType, imageUuidT, imageUuidA)

    print('Finish')