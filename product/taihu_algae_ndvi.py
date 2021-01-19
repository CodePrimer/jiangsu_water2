# -*- coding: utf-8 -*-
"""
太湖蓝藻监测产品

"""

import os
import sys
import uuid
import time
import json
import shutil

import gdal
import osr
import numpy as np
import pymysql

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from tools.RasterRander.RgbComposite import RgbComposite
from tools.RasterRander.UniqueValues import UniqueValues

# 通用常量

# 太湖总面积（平方千米）
TAIHU_AREA = 2400

# 太湖区域范围
TAIHU_BOUNDS = (195203.762, 3418022.181, 282703.762, 3505522.181)

# 湖区掩膜对应值
LAKE_MASK_DATA_DICT = {1: "zhushanhu", 2: "meilianghu", 3: "gonghu", 4: "westCoast", 5: "southCoast", 6: "centerLake",
                       7: "eastCoast", 8: "eastTaihu"}

# 行政区掩膜对应值
ADMIN_MASK_DATA_DICT = {1: 'wuxi', 2: 'changzhou', 3: 'suzhou'}

# 蓝藻强度分级ndvi切分阈值
ALGAE_INTENSITY_THRESHOLD = [0.2, 0.4]

# 各数据源红光波段云掩膜阈值
CLOUD_THRESHOLD_DICT = {'TERRA_MODIS_250': {'bandIndex': 1, 'threshold': 3500},
                        'AQUA_MODIS_250': {'bandIndex': 1, 'threshold': 3500},
                        'NPP_VIIRS_375': {'bandIndex': 1, 'threshold': 400},
                        'SENTINEL2A_MSI_10': {'bandIndex': 3, 'threshold': 500},
                        'SENTINEL2B_MSI_10': {'bandIndex': 3, 'threshold': 500},
                        'SENTINEL2A_MSI_20': {'bandIndex': 3, 'threshold': 500},
                        'SENTINEL2B_MSI_20': {'bandIndex': 3, 'threshold': 500},
                        'SENTINEL3A_OLCI_300': {'bandIndex': 5, 'threshold': 500},
                        'SENTINEL3B_OLCI_300': {'bandIndex': 5, 'threshold': 500},
                        'H8_AHI_1000': {'bandIndex': 3, 'threshold': 2000},
                        'COMS_GOCI_500': {'bandIndex': 4, 'threshold': 120}}

# 各数据源ndvi判识蓝藻阈值 bandIndex[近红, 红]
ALGAE_NDVI_THRESHOLD = {'TERRA_MODIS_250': {'bandIndex': [2, 1], 'threshold': 0.1},
                        'AQUA_MODIS_250': {'bandIndex': [2, 1], 'threshold': 0.1},
                        'NPP_VIIRS_375': {'bandIndex': [2, 1], 'threshold': 0.1},
                        'SENTINEL2A_MSI_10': {'bandIndex': [4, 3], 'threshold': 0.1},
                        'SENTINEL2B_MSI_10': {'bandIndex': [4, 3], 'threshold': 0.1},
                        'SENTINEL2A_MSI_20': {'bandIndex': [7, 3], 'threshold': 0.1},
                        'SENTINEL2B_MSI_20': {'bandIndex': [7, 3], 'threshold': 0.1},
                        'SENTINEL3A_OLCI_300': {'bandIndex': [11, 5], 'threshold': 0.1},
                        'SENTINEL3B_OLCI_300': {'bandIndex': [11, 5], 'threshold': -0.1},
                        'H8_AHI_1000': {'bandIndex': [4, 3], 'threshold': 0.1},
                        'COMS_GOCI_500': {'bandIndex': [7, 4], 'threshold': 0.1}}

# 各数据源假彩色合成
FALSE_COLOR_COMPOSE = {'TERRA_MODIS_250': [1, 2, 1],
                       'AQUA_MODIS_250': [1, 2, 1],
                       'NPP_VIIRS_375': [1, 2, 1],
                       'SENTINEL2A_MSI_10': [4, 3, 2],
                       'SENTINEL2B_MSI_10': [4, 3, 2],
                       'SENTINEL2A_MSI_20': [7, 3, 2],
                       'SENTINEL2B_MSI_20': [7, 3, 2],
                       'SENTINEL3A_OLCI_300': [11, 5, 3],
                       'SENTINEL3B_OLCI_300': [11, 5, 3],
                       'H8_AHI_1000': [4, 3, 2],
                       'COMS_GOCI_500': [7, 4, 2]}

# 各数据源真彩色合成
TRUE_COLOR_COMPOSE = {'TERRA_MODIS_250': [],
                      'AQUA_MODIS_250': [],
                      'NPP_VIIRS_375': [],
                      'SENTINEL2A_MSI_10': [3, 2, 1],
                      'SENTINEL2B_MSI_10': [3, 2, 1],
                      'SENTINEL2A_MSI_20': [3, 2, 1],
                      'SENTINEL2B_MSI_20': [3, 2, 1],
                      'SENTINEL3A_OLCI_300': [5, 3, 1],
                      'SENTINEL3B_OLCI_300': [5, 3, 1],
                      'H8_AHI_1000': [3, 2, 1],
                      'COMS_GOCI_500': [4, 2, 1]}

TILE_LEVEL = '8-13'

# 加载全局配置文件
globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


class AlgaeTaihu(object):
    """
    太湖蓝藻产品类
    """

    def __init__(self, inputPath, modelUuid):
        # 输入
        self.inputPath = inputPath         # 输入预处理文件路径
        self.modelUuid = modelUuid         # 模型标识

        # 参数
        self.satellite = None           # 卫星名
        self.sensor = None              # 传感器名
        self.dataIdentify = None        # 数据源标识 卫星_传感器_分辨率
        self.res = None                 # 结果文件像元分辨率（米）
        self.issue = None               # 期号
        self.cloudThreshold = None      # 云掩膜红光波段阈值
        self.algaeThreshold = None      # 蓝藻NDVI阈值
        self.falseColorCompose = None   # 假彩色合成组合
        self.trueColorCompose = None    # 真彩色合成组合
        self.editDependDir = ''         # 编辑所需文件夹
        self.jsonData = {}              # json文件中相关变量存储

        # 输出
        self.outputDir = ''             # 当期输出文件夹目录
        self.l2TifPath = ''             # 裁切太湖区域后文件路径
        self.cloudTifPath = ''          # 云产品结果路径
        self.ndviTifPath = ''           # 植被指数结果路径
        self.algaeTifPath = ''          # 蓝藻产品结果路径（二值结果）
        self.intensityTifPath = ''      # 蓝藻强度产品结果路径（分级结果）
        self.statistic = {}             # 蓝藻产品相关统计信息
        self.tileDict = {}              # 切片相关信息，入库用

    def algaeInit(self):
        """
        根据不同的输入参数初始化类。
        1.像元分辨率。2.云掩膜阈值。3.ndvi判别蓝藻阈值。4.假彩色合成波段。5.真彩色合成波段。
        6.编辑所需依赖文件夹路径。
        :return:
        """
        baseName = os.path.basename(self.inputPath)
        self.satellite = baseName.split('_')[0]
        self.sensor = baseName.split('_')[1]
        self.res = float(baseName.split('_')[4])
        self.issue = baseName.split('_')[3]
        self.dataIdentify = '_'.join([self.satellite, self.sensor, baseName.split('_')[4]]).upper()
        # 获取当前云掩膜阈值
        if self.dataIdentify in CLOUD_THRESHOLD_DICT.keys():
            self.cloudThreshold = CLOUD_THRESHOLD_DICT[self.dataIdentify]
        # 获取当前蓝藻判别阈值
        if self.dataIdentify in ALGAE_NDVI_THRESHOLD.keys():
            self.algaeThreshold = ALGAE_NDVI_THRESHOLD[self.dataIdentify]
        # 获取当前假彩色波段组合
        if self.dataIdentify in FALSE_COLOR_COMPOSE.keys():
            self.falseColorCompose = FALSE_COLOR_COMPOSE[self.dataIdentify]
        # 获取当前真彩色波段组合
        if self.dataIdentify in FALSE_COLOR_COMPOSE.keys():
            self.trueColorCompose = TRUE_COLOR_COMPOSE[self.dataIdentify]

        # 初始化各参数检查
        checkList = [self.satellite, self.sensor, self.dataIdentify, self.res, self.issue,
                     self.cloudThreshold, self.algaeThreshold, self.falseColorCompose, self.trueColorCompose]
        for each in checkList:
            if each is None:
                return False

        # 创建输出文件夹
        outputRootDir = globalCfg['output_path']
        timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        self.outputDir = os.path.join(outputRootDir, self.modelUuid, timeStamp)
        os.makedirs(self.outputDir)

        return True

    def clipRegion(self):
        """输入数据转utm投影，并裁切研究区"""
        dependDir = globalCfg['depend_path']
        utmPrjFile = os.path.join(dependDir, 'prj', 'UTM_Zone_51N.prj')
        if not os.path.exists(utmPrjFile):
            raise FileNotFoundError('Cannot Found Path: %s' % utmPrjFile)
        l2TifName = os.path.basename(self.inputPath).split('.')[0] + '_taihu_algae_ndvi.l2.tif'
        self.l2TifPath = os.path.join(self.outputDir, l2TifName)
        gdal.Warp(self.l2TifPath, self.inputPath, dstSRS=utmPrjFile, format='GTiff', outputBounds=TAIHU_BOUNDS,
                  dstNodata=65535, xRes=self.res, yRes=self.res)

    def cloudProduct(self):
        """生成云产品"""
        ds = gdal.Open(self.l2TifPath, gdal.GA_ReadOnly)
        width = ds.RasterXSize
        height = ds.RasterYSize
        redBandIndex = CLOUD_THRESHOLD_DICT[self.dataIdentify]['bandIndex']
        bandR = ds.GetRasterBand(redBandIndex).ReadAsArray()
        cloudArray = np.zeros((height, width), dtype=np.uint8)
        # 云检测阈值
        cloudArray[np.logical_and(bandR > CLOUD_THRESHOLD_DICT[self.dataIdentify]['threshold'], bandR != 65535)] = 1

        cloudTifName = os.path.basename(self.inputPath).split('.')[0] + '_taihu_algae_ndvi.cloud.tif'
        self.cloudTifPath = os.path.join(self.outputDir, cloudTifName)
        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(self.cloudTifPath, width, height, 1, gdal.GDT_Byte)
        outDs.SetGeoTransform(ds.GetGeoTransform())
        outDs.SetProjection(ds.GetProjection())
        outDs.GetRasterBand(1).WriteArray(cloudArray)
        ds = None
        outDs = None
        # 云量计算
        cloudPercent = round(len(cloudArray[cloudArray == 1].tolist()) / (width * height) * 100)
        self.statistic['cloud'] = cloudPercent

    def ndviProduct(self):
        """生成ndvi产品"""
        ds = gdal.Open(self.l2TifPath, gdal.GA_ReadOnly)
        width = ds.RasterXSize
        height = ds.RasterYSize
        nirBandIndex = ALGAE_NDVI_THRESHOLD[self.dataIdentify]['bandIndex'][0]
        redBandIndex = ALGAE_NDVI_THRESHOLD[self.dataIdentify]['bandIndex'][1]
        bandR = ds.GetRasterBand(redBandIndex).ReadAsArray()
        bandNir = ds.GetRasterBand(nirBandIndex).ReadAsArray()
        ndviArray = (bandNir * 1.0 - bandR) / (bandNir * 1.0 + bandR)

        ndviTifName = os.path.basename(self.inputPath).split('.')[0] + '_taihu_algae_ndvi.org.tif'
        self.ndviTifPath = os.path.join(self.outputDir, ndviTifName)
        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(self.ndviTifPath, width, height, 1, gdal.GDT_Float32)
        outDs.SetGeoTransform(ds.GetGeoTransform())
        outDs.SetProjection(ds.GetProjection())
        outDs.GetRasterBand(1).WriteArray(ndviArray)
        ds = None
        outDs = None

    def algaeProduct(self):
        """蓝藻产品生产"""
        # 掩膜相关文件位置
        dependDir = os.path.join(globalCfg['depend_path'], 'taihu', str(int(self.res)))
        if not os.path.exists(dependDir):
            raise FileNotFoundError('Cannot Found Path: %s' % dependDir)

        boundaryMaskPath = os.path.join(dependDir, 'taihu_mask_utm[0].tif')     # 太湖边界掩膜TIF
        regionMaskPath = os.path.join(dependDir, 'taihu_region.tif')  # 太湖分湖区掩膜TIF
        if not os.path.exists(boundaryMaskPath):
            raise FileNotFoundError('Cannot Found Path: %s' % boundaryMaskPath)
        if not os.path.exists(regionMaskPath):
            raise FileNotFoundError('Cannot Found Path: %s' % regionMaskPath)

        # 边界缩放掩膜数组
        ds = gdal.Open(boundaryMaskPath, gdal.GA_ReadOnly)
        boundaryBufferMaskArray = ds.GetRasterBand(1).ReadAsArray()             # 值1代表需要区域
        ds = None

        # 湖区掩膜数组
        ds = gdal.Open(regionMaskPath, gdal.GA_ReadOnly)
        lakeMaskArray = ds.GetRasterBand(1).ReadAsArray()               # 各湖区栅格有不同的值
        ds = None
        # 默认掩膜东太湖
        lakeMask = {"zhushanhu": 0, "meilianghu": 0, "gonghu": 0, "westCoast": 0, "southCoast": 0, "centerLake": 0,
                    "eastCoast": 0, "eastTaihu": 1}
        for v in LAKE_MASK_DATA_DICT.keys():
            if lakeMask[LAKE_MASK_DATA_DICT[v]]:
                boundaryBufferMaskArray[lakeMaskArray == v] = 0     # 遍历列表将要掩膜的湖区值变为0

        # 加载ndvi数组
        ds = gdal.Open(self.ndviTifPath, gdal.GA_ReadOnly)
        width = ds.RasterXSize
        height = ds.RasterYSize
        ndviArray = ds.GetRasterBand(1).ReadAsArray()
        trans = ds.GetGeoTransform()
        proj = ds.GetProjection()
        ds = None

        algaeArray = np.zeros((height, width), dtype=np.uint8)
        algaeThreshold = self.algaeThreshold['threshold']
        algaeArray[np.logical_and(ndviArray > algaeThreshold, boundaryBufferMaskArray == 1)] = 1

        algaeTifName = os.path.basename(self.inputPath).split('.')[0] + '_taihu_algae_ndvi.tif'
        self.algaeTifPath = os.path.join(self.outputDir, algaeTifName)
        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(self.algaeTifPath, width, height, 1, gdal.GDT_Byte)
        outDs.SetGeoTransform(trans)
        outDs.SetProjection(proj)
        outDs.GetRasterBand(1).WriteArray(algaeArray)
        outDs = None

        self.statistic['algaeThreshold'] = algaeThreshold
        self.statistic['boundaryThreshold'] = 0
        self.statistic['lakeMask'] = lakeMask

    def intensityProduct(self):
        """生成蓝藻强度产品"""
        # 加载ndvi数组
        ds = gdal.Open(self.ndviTifPath, gdal.GA_ReadOnly)
        width = ds.RasterXSize
        height = ds.RasterYSize
        ndviArray = ds.GetRasterBand(1).ReadAsArray()
        trans = ds.GetGeoTransform()
        proj = ds.GetProjection()
        ds = None

        # 加载蓝藻数组
        ds = gdal.Open(self.algaeTifPath, gdal.GA_ReadOnly)
        algaeArray = ds.GetRasterBand(1).ReadAsArray()
        ds = None

        insArray = np.zeros((height, width), dtype=np.uint8)  # 初始化强度数组

        # 计算动态阈值 低(0-40%) 中(40%-80%) 高(80%-100%)
        ndviList = ndviArray[algaeArray == 1].tolist()
        # 如果藻像元小于2个
        if len(ndviList) == 0:
            ndviMax = 0
            ndviMin = 0
            ndviMean = 0
            insThreshold1 = 0
            insThreshold2 = 0
        elif len(ndviList) == 1:
            ndviMax = max(ndviList)
            ndviMin = min(ndviList)
            ndviMean = np.mean(ndviList)
            insThreshold1 = 0
            insThreshold2 = 0
        else:
            ndviMax = max(ndviList)
            ndviMin = min(ndviList)
            ndviMean = np.mean(ndviList)
            # insThreshold1 = (ndviMax - ndviMin) * ALGAE_INTENSITY_THRESHOLD[0] + ndviMin
            # insThreshold2 = (ndviMax - ndviMin) * ALGAE_INTENSITY_THRESHOLD[1] + ndviMin
            insThreshold1 = ALGAE_INTENSITY_THRESHOLD[0]
            insThreshold2 = ALGAE_INTENSITY_THRESHOLD[1]

            insArray[
                np.logical_and(np.logical_and(ndviArray >= ndviMin, ndviArray < insThreshold1), algaeArray == 1)] = 1
            insArray[np.logical_and(np.logical_and(ndviArray >= insThreshold1, ndviArray < insThreshold2),
                                    algaeArray == 1)] = 2
            insArray[
                np.logical_and(np.logical_and(ndviArray >= insThreshold2, ndviArray <= ndviMax), algaeArray == 1)] = 3

        intensityTifName = os.path.basename(self.inputPath).split('.')[0] + '_taihu_algae_intensity.tif'
        self.intensityTifPath = os.path.join(self.outputDir, intensityTifName)
        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(self.intensityTifPath, width, height, 1, gdal.GDT_Byte)
        outDs.SetGeoTransform(trans)
        outDs.SetProjection(proj)
        outDs.GetRasterBand(1).WriteArray(insArray)
        ds = None
        outDs = None

        # 相关信息存储
        self.statistic['insThreshold1'] = float('%.3f' % insThreshold1)
        self.statistic['insThreshold2'] = float('%.3f' % insThreshold2)
        self.statistic['ndviMax'] = float('%.2f' % ndviMax)
        self.statistic['ndviMin'] = float('%.2f' % ndviMin)
        self.statistic['ndviMean'] = float('%.2f' % ndviMean)

    def productStatistic(self):
        """产品统计"""

        dependDir = os.path.join(globalCfg['depend_path'], 'taihu', str(int(self.res)))
        if not os.path.exists(dependDir):
            raise FileNotFoundError('Cannot Found Path: %s' % dependDir)

        adminMaskPath = os.path.join(dependDir, 'taihu_admin.tif')  # 太湖边界掩膜TIF
        regionMaskPath = os.path.join(dependDir, 'taihu_region.tif')  # 太湖分湖区掩膜TIF
        if not os.path.exists(adminMaskPath):
            raise FileNotFoundError('Cannot Found Path: %s' % adminMaskPath)
        if not os.path.exists(regionMaskPath):
            raise FileNotFoundError('Cannot Found Path: %s' % regionMaskPath)

        # 1.统计蓝藻产品
        ds = gdal.Open(self.algaeTifPath, gdal.GA_ReadOnly)
        algaeArray = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        pixelArea = (self.res / 1000) * (self.res / 1000)       # 像元面积
        totalArea = len(algaeArray[algaeArray == 1].tolist()) * pixelArea
        totalArea = round(totalArea)  # 总面积
        totalPercent = float('%.1f' % ((totalArea / 2400) * 100))  # 总占比

        regionArea = {}      # 分湖区面积统计结果
        ds = gdal.Open(regionMaskPath, gdal.GA_ReadOnly)
        regionMaskArray = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        for v in LAKE_MASK_DATA_DICT.keys():
            curRegionArray = regionMaskArray == v
            curArea = len(algaeArray[np.logical_and(algaeArray == 1, curRegionArray)].tolist()) * pixelArea
            regionArea[LAKE_MASK_DATA_DICT[v]] = curArea

        lakeStat = {}       # 湖区统计是否勾选
        for key in regionArea.keys():
            lakeStat[key] = 0
            if regionArea[key] > 0:
                lakeStat[key] = 1

        adminArea = {}      # 行政区面积
        adminPercent = {}   # 行政区占比
        ds = gdal.Open(adminMaskPath, gdal.GA_ReadOnly)
        adminMaskArray = ds.GetRasterBand(1).ReadAsArray()
        ds = None

        for v in ADMIN_MASK_DATA_DICT.keys():
            curAdminArray = adminMaskArray == v
            curArea = len(algaeArray[np.logical_and(algaeArray == 1, curAdminArray)].tolist()) * pixelArea
            adminArea[ADMIN_MASK_DATA_DICT[v]] = curArea

        # 约减行政区面积
        tempIndex = 0
        tempAreaSum = 0
        for each in adminArea.keys():
            tempIndex += 1
            if not (tempIndex == len(adminArea)):
                adminArea[each] = round(adminArea[each])
                tempAreaSum += adminArea[each]
            else:
                adminArea[each] = totalArea - tempAreaSum

        # 计算行政区百分比
        if totalArea == 0:
            adminPercent['wuxi'] = 0
            adminPercent['changzhou'] = 0
            adminPercent['suzhou'] = 0
        else:
            adminPercent['wuxi'] = round((adminArea['wuxi']) / totalArea * 100)
            adminPercent['changzhou'] = round((adminArea['changzhou']) / totalArea * 100)
            adminPercent['suzhou'] = 100 - adminPercent['wuxi'] - adminPercent['changzhou']

        # 2.统计强度产品
        ds = gdal.Open(self.intensityTifPath, gdal.GA_ReadOnly)
        insArray = ds.GetRasterBand(1).ReadAsArray()
        ds = None

        # 低聚区面积
        lowArea = len(insArray[insArray == 1].tolist()) * pixelArea
        lowArea = round(lowArea)
        # 中聚区面积
        midArea = len(insArray[insArray == 2].tolist()) * pixelArea
        midArea = round(midArea)
        # 高聚区面积
        highArea = totalArea - lowArea - midArea

        # 计算聚集区百分比
        if totalArea == 0:
            lowPercent = 0
            midPercent = 0
            highPercent = 0
        else:
            lowPercent = round(lowArea / totalArea * 100)
            midPercent = round(midArea / totalArea * 100)
            highPercent = 100 - lowPercent - midPercent

        self.statistic['totalArea'] = totalArea
        self.statistic['totalPercent'] = totalPercent
        self.statistic['adminArea'] = adminArea
        self.statistic['adminPercent'] = adminPercent
        self.statistic['regionArea'] = regionArea
        self.statistic['lakeStat'] = lakeStat
        self.statistic['lowArea'] = lowArea
        self.statistic['midArea'] = midArea
        self.statistic['highArea'] = highArea
        self.statistic['lowArea'] = lowArea
        self.statistic['midArea'] = midArea
        self.statistic['highArea'] = highArea
        self.statistic['lowPercent'] = lowPercent
        self.statistic['midPercent'] = midPercent
        self.statistic['highPercent'] = highPercent

    def toJson(self):
        """生成前端渲染json文件"""
        # 转为WGS 84坐标
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)

        ndviProjName = os.path.basename(self.ndviTifPath).replace('.tif', '_wgs84.tif')
        ndviProjPath = os.path.join(self.outputDir, ndviProjName)
        ds = gdal.Warp(ndviProjPath, self.ndviTifPath, dstSRS=srs, format='GTiff')
        ndviArray = ds.GetRasterBand(1).ReadAsArray()
        ds = None

        algaeProjName = os.path.basename(self.algaeTifPath).replace('.tif', '_wgs84.tif')
        algaeProjPath = os.path.join(self.outputDir, algaeProjName)
        ds = gdal.Warp(algaeProjPath, self.algaeTifPath, dstSRS=srs, format='GTiff')
        algaeArray = ds.GetRasterBand(1).ReadAsArray()
        xSize = ds.RasterXSize
        ySize = ds.RasterYSize
        geoTrans = ds.GetGeoTransform()
        leftTopX = geoTrans[0]
        leftTopY = geoTrans[3]
        rightDownX = leftTopX + geoTrans[1] * (xSize - 1)
        rightDownY = leftTopY + geoTrans[5] * (ySize - 1)
        lonMin = min([leftTopX, rightDownX])
        lonMax = max([leftTopX, rightDownX])
        latMin = min([leftTopY, rightDownY])
        latMax = max([leftTopY, rightDownY])
        ds = None

        data = []  # json文件中data
        index = []  # json文件中index
        for i in range(ySize):
            for j in range(xSize):
                if algaeArray[i][j] == 1:
                    data.append(int(ndviArray[i][j] * 100))
                    index.append(i * xSize + j)
        jsonData = {'data': data, 'index': index, 'xsize': xSize, 'ysize': ySize, 'lonMin': lonMin, 'lonMax': lonMax,
                    'latMin': latMin, 'latMax': latMax, 'scale': 0.01, 'offset': 0}
        self.jsonData = {'xsize': xSize, 'ysize': ySize, 'lonMin': lonMin, 'lonMax': lonMax, 'latMin': latMin,
                         'latMax': latMax, 'scale': 0.01, 'offset': 0}

        for key in self.statistic.keys():
            jsonData[key] = self.statistic[key]

        jsonText = json.dumps(jsonData)
        outJsonName = os.path.basename(self.algaeTifPath).replace('.tif', '.json')
        outJsonPath = os.path.join(self.outputDir, outJsonName)
        with open(outJsonPath, "w", encoding='utf-8') as f:
            f.write(jsonText + "\n")

        # 删除转wgs84的临时文件
        try:
            if os.path.exists(algaeProjPath):
                os.remove(algaeProjPath)
            if os.path.exists(ndviProjPath):
                os.remove(ndviProjPath)
        except Exception as e:
            raise Exception(e)

    def tileServer(self):
        """生成对应切片文件"""

        basename = os.path.basename(self.inputPath).split('.')[0]
        # 1.假彩色底图切片 falseColor
        if self.dataIdentify in FALSE_COLOR_COMPOSE.keys():
            if FALSE_COLOR_COMPOSE[self.dataIdentify]:
                falseColorTifName = os.path.basename(self.l2TifPath).replace('.tif', '_false.tif')
                falseColorTifPath = os.path.join(self.outputDir, falseColorTifName)
                if self.dataIdentify in ['SENTINEL2A_MSI_10', 'SENTINEL2B_MSI_10',
                                         'SENTINEL2A_MSI_20', 'SENTINEL2B_MSI_20',
                                         'SENTINEL3A_OLCI_300', 'SENTINEL3B_OLCI_300',
                                         'TERRA_MODIS_250', 'AQUA_MODIS_250']:
                    RgbComposite.Compose(self.l2TifPath, FALSE_COLOR_COMPOSE[self.dataIdentify], noDataValue=65535,
                                         returnMode='GEOTIFF', outputPath=falseColorTifPath,
                                         stretchType='LinearPercent', stretchParam=[0], isAlpha=True)
                else:
                    RgbComposite.Compose(self.l2TifPath, FALSE_COLOR_COMPOSE[self.dataIdentify], noDataValue=0,
                                         returnMode='GEOTIFF', outputPath=falseColorTifPath,
                                         stretchType='LinearPercent', stretchParam=[0], isAlpha=True)
                self.tileDict['falseColor'] = {'tif': falseColorTifPath, 'name': basename+'_falseColor'}

        # 2.假彩色底图增强切片 falseColor_enhance1
        if self.dataIdentify in FALSE_COLOR_COMPOSE.keys():
            if FALSE_COLOR_COMPOSE[self.dataIdentify]:
                fcEnhanceTifName = os.path.basename(self.l2TifPath).replace('.tif', '_falseEnhance.tif')
                fcEnhanceTifPath = os.path.join(self.outputDir, fcEnhanceTifName)
                if self.dataIdentify in ['SENTINEL2A_MSI_10', 'SENTINEL2B_MSI_10',
                                         'SENTINEL2A_MSI_20', 'SENTINEL2B_MSI_20',
                                         'SENTINEL3A_OLCI_300', 'SENTINEL3B_OLCI_300',
                                         'TERRA_MODIS_250', 'AQUA_MODIS_250']:
                    RgbComposite.Compose(self.l2TifPath, FALSE_COLOR_COMPOSE[self.dataIdentify], noDataValue=65535,
                                         returnMode='GEOTIFF', outputPath=fcEnhanceTifPath,
                                         stretchType='LinearPercent', stretchParam=[2], isAlpha=True)
                else:
                    RgbComposite.Compose(self.l2TifPath, FALSE_COLOR_COMPOSE[self.dataIdentify], noDataValue=0,
                                         returnMode='GEOTIFF', outputPath=fcEnhanceTifPath,
                                         stretchType='LinearPercent', stretchParam=[2], isAlpha=True)
                self.tileDict['falseColorEnhance'] = {'tif': fcEnhanceTifPath, 'name': basename+'_falseColor_enhance1'}

        # 3.真彩色底图切片 trueColor
        if self.dataIdentify in TRUE_COLOR_COMPOSE.keys():
            if TRUE_COLOR_COMPOSE[self.dataIdentify]:
                trueColorTifName = os.path.basename(self.l2TifPath).replace('.tif', '_true.tif')
                trueColorTifPath = os.path.join(self.outputDir, trueColorTifName)
                if self.dataIdentify in ['SENTINEL2A_MSI_10', 'SENTINEL2B_MSI_10',
                                         'SENTINEL2A_MSI_20', 'SENTINEL2B_MSI_20',
                                         'SENTINEL3A_OLCI_300', 'SENTINEL3B_OLCI_300']:
                    RgbComposite.Compose(self.l2TifPath, TRUE_COLOR_COMPOSE[self.dataIdentify], noDataValue=65535,
                                         returnMode='GEOTIFF', outputPath=trueColorTifPath,
                                         stretchType='LinearPercent', stretchParam=[0], isAlpha=True)
                else:
                    RgbComposite.Compose(self.l2TifPath, TRUE_COLOR_COMPOSE[self.dataIdentify], noDataValue=0,
                                         returnMode='GEOTIFF', outputPath=trueColorTifPath,
                                         stretchType='LinearPercent', stretchParam=[0], isAlpha=True)
                self.tileDict['trueColor'] = {'tif': trueColorTifPath, 'name': basename+'_trueColor'}

        # 4.真彩色底图增强切片 trueColor_enhance1
        if self.dataIdentify in TRUE_COLOR_COMPOSE.keys():
            if TRUE_COLOR_COMPOSE[self.dataIdentify]:
                tcEnhanceTifName = os.path.basename(self.l2TifPath).replace('.tif', '_trueEnhance.tif')
                tcEnhanceTifPath = os.path.join(self.outputDir, tcEnhanceTifName)
                if self.dataIdentify in ['SENTINEL2A_MSI_10', 'SENTINEL2B_MSI_10',
                                         'SENTINEL2A_MSI_20', 'SENTINEL2B_MSI_20',
                                         'SENTINEL3A_OLCI_300', 'SENTINEL3B_OLCI_300']:
                    RgbComposite.Compose(self.l2TifPath, TRUE_COLOR_COMPOSE[self.dataIdentify], noDataValue=65535,
                                         returnMode='GEOTIFF', outputPath=tcEnhanceTifPath,
                                         stretchType='LinearPercent', stretchParam=[2], isAlpha=True)
                else:
                    RgbComposite.Compose(self.l2TifPath, TRUE_COLOR_COMPOSE[self.dataIdentify], noDataValue=0,
                                         returnMode='GEOTIFF', outputPath=tcEnhanceTifPath,
                                         stretchType='LinearPercent', stretchParam=[2], isAlpha=True)
                self.tileDict['trueColorEnhance'] = {'tif': tcEnhanceTifPath, 'name': basename+'_trueColor_enhance1'}

        # 5.云产品切片 cloud
        cloudTifName = os.path.basename(self.cloudTifPath).replace('.tif', '_render.tif')
        cloudTifPath = os.path.join(self.outputDir, cloudTifName)
        colorTable = {1: (255, 255, 255)}
        UniqueValues.Render(self.cloudTifPath, colorTable, returnMode='GEOTIFF', outputPath=cloudTifPath, isAlpha=True)
        self.tileDict['cloud'] = {'tif': cloudTifPath, 'name': basename+'_cloud', 'legendType': '1',
                                  'legendColor': [(255, 255, 255)], 'legendName': ['云']}

        # 6.蓝藻产品切片
        algaeTifName = os.path.basename(self.algaeTifPath).replace('.tif', '_render.tif')
        algaeTifPath = os.path.join(self.outputDir, algaeTifName)
        colorTable = {1: (255, 251, 0)}
        UniqueValues.Render(self.algaeTifPath, colorTable, returnMode='GEOTIFF', outputPath=algaeTifPath, isAlpha=True)
        self.tileDict['taihu_algae_ndvi'] = {'tif': algaeTifPath, 'name': basename+'_taihu_algae_ndvi',
                                             'legendType': '1', 'legendColor': [(255, 251, 0)], 'legendName': ['水华']}

        # 7.蓝藻强度产品切片
        intensityTifName = os.path.basename(self.intensityTifPath).replace('.tif', '_render.tif')
        intensityTifPath = os.path.join(self.outputDir, intensityTifName)
        colorTable = {1: (0, 255, 102), 2: (255, 255, 0), 3: (255, 153, 0)}
        UniqueValues.Render(self.intensityTifPath, colorTable, returnMode='GEOTIFF', outputPath=intensityTifPath,
                            isAlpha=True)
        self.tileDict['algaeClassify'] = {'tif': intensityTifPath, 'name': basename+'_classify', 'legendType': '1',
                                          'legendColor': [(0, 255, 102), (255, 255, 0), (255, 153, 0)],
                                          'legendName': ['轻度', '中度', '重度']}

        # 调用gdal2tiles工具进行切片
        pythonPath = globalCfg['python_path']
        gdal2tilesPath = globalCfg['gdal2tiles_path']
        tileOutRootDir = globalCfg['tile_server_path']
        for key in self.tileDict.keys():
            tileTif = self.tileDict[key]['tif']
            tileOutDir = os.path.join(tileOutRootDir, self.tileDict[key]['name'])
            if os.path.exists(tileOutDir):
                shutil.rmtree(tileOutDir)
            cmd = '%s %s -z %s -w all %s %s' % (pythonPath, gdal2tilesPath, TILE_LEVEL, tileTif, tileOutDir)
            os.system(cmd)
            os.remove(tileTif)
            self.tileDict[key]['path'] = tileOutDir

    def executeSql(self):
        """执行入库操作"""
        # 连接数据库
        conn = pymysql.connect(
            db=globalCfg['database'],
            user=globalCfg['database_user'],
            password=globalCfg['database_passwd'],
            host=globalCfg['database_host'],
            port=globalCfg['database_port']
        )

        # t_export_image ==================================================
        # 先查询数据库是否有这期数据
        cursor = conn.cursor()
        sqlStr = 'SELECT * FROM ' + globalCfg['database_table_export_image'] + \
                 ' WHERE model_uuid=%s and name=%s and is_deleted=0;'
        algaeTifName = os.path.basename(self.algaeTifPath)
        sqlData = (self.modelUuid, algaeTifName)
        cursor.execute(sqlStr, sqlData)
        sqlRes = cursor.fetchall()
        if len(sqlRes) > 0:
            print('already exist product.')
        else:
            image_uuid = str(uuid.uuid4())
            db_path = self.algaeTifPath.replace('\\', '/').replace('/mnt/resource/', '')
            db_lat_lr = self.jsonData['latMin']
            db_lon_lr = self.jsonData['lonMax']
            db_lon_ul = self.jsonData['lonMin']
            db_lat_ul = self.jsonData['latMax']
            db_acquire_time = '%s-%s-%s %s:%s:%s' % \
                              (self.issue[0:4], self.issue[4:6], self.issue[6:8], self.issue[8:10], self.issue[10:12],
                               self.issue[12:14])
            db_cloud = self.statistic['cloud']
            db_area = self.statistic['totalArea']
            db_process_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            db_threshold = self.statistic['algaeThreshold']
            sqlStr = 'INSERT INTO ' + globalCfg['database_table_export_image'] + \
                     ' (uuid,name,path,type,model_type,satellite,sensor,lat_lr,lon_lr,lon_ul,lat_ul,' + \
                     'acquire_time,cloud,area,process_time,is_deleted,model_uuid,colorbar_min,colorbar_max,' \
                     'colorbar_tick,colorbar_color,unit,is_edit,is_edited,threshold) ' + \
                     'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
            sqlData = (image_uuid, algaeTifName, db_path, 'tif', 'algae', self.satellite, self.sensor, db_lat_lr,
                       db_lon_lr, db_lon_ul, db_lat_ul, db_acquire_time, db_cloud, db_area, db_process_time, 0,
                       self.modelUuid, '无', '有', '水华', '#ffff00', '', 0, 1, db_threshold)
            cursor.execute(sqlStr, sqlData)
            conn.commit()

            # # t_tile_server ==================================================
            # for key in self.tileDict:
            #     db_name = self.tileDict[key]['name']
            #     db_path = self.tileDict[key]['path'].replace('\\', '/')
            #     db_update_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            #     db_type = key
            #     db_legend_type = '0'
            #     db_legend_color = ''
            #     db_legend_name = ''
            #     if 'legendColor' in self.tileDict[key].keys():
            #         db_legend_type = self.tileDict[key]['legendType']
            #         db_legend_color = ','.join([str(i) for i in self.tileDict[key]['legendColor']])
            #         db_legend_name = ','.join(self.tileDict[key]['legendName'])
            #
            #     sqlStr = 'SELECT * FROM ' + globalCfg['database_table_tile_server'] + \
            #              ' WHERE image_uuid=%s and type=%s;'
            #     sqlData = (image_uuid, db_type)
            #     cursor.execute(sqlStr, sqlData)
            #     sqlRes = cursor.fetchall()
            #     if len(sqlRes) > 0:
            #         sqlStr = 'UPDATE ' + globalCfg['database_table_tile_server'] + \
            #                  ' SET (name,path,update_time,legend_type,legend_color,legend_name) ' + \
            #                  'VALUES (%s,%s,%s,%s,%s,%s,%s);'
            #         sqlData = (db_name, db_path, db_update_time, db_legend_type, db_legend_color, db_legend_name)
            #     else:
            #         db_uuid = str(uuid.uuid4())
            #         sqlStr = 'INSERT INTO ' + globalCfg['database_table_tile_server'] + \
            #                  ' (uuid,name,path,type,acquire_time,update_time,image_uuid,legend_type,legend_color,' \
            #                  'legend_name) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);'
            #         sqlData = (db_uuid, db_name, db_path, db_type, db_acquire_time, db_update_time, image_uuid,
            #                    db_legend_type, db_legend_color, db_legend_name)
            #     cursor.execute(sqlStr, sqlData)
            #     conn.commit()

            cursor.close()
            conn.close()

    @staticmethod
    def main(inputFile, modelUuid):

        algaeObj = AlgaeTaihu(inputFile, modelUuid)
        flag = algaeObj.algaeInit()  # 初始化参数
        if not flag:
            return

        try:
            # 裁切研究区
            algaeObj.clipRegion()

            # 生成云产品 计算云量
            algaeObj.cloudProduct()

            # 生成ndvi产品
            algaeObj.ndviProduct()

            # 生成蓝藻产品
            algaeObj.algaeProduct()

            # 生成蓝藻强度产品
            algaeObj.intensityProduct()

            # 蓝藻统计
            algaeObj.productStatistic()

            # 生成编辑所需json文件
            algaeObj.toJson()

            # 切片
            algaeObj.tileServer()

            # 数据入库
            algaeObj.executeSql()

        except Exception as e:
            print(e)


def call_main(inFile, modelId):
    AlgaeTaihu.main(inFile, modelId)


if __name__ == '__main__':

    # # 输入栅格数据
    # inFile = r'F:\Sentinel2A_MSI_L2_202101081041_10_0209_089.tif'
    # # 当前算法uuid
    # modelId = 'abc'

    inFile = sys.argv[1]
    modelId = sys.argv[2]

    startTime = time.time()

    AlgaeTaihu.main(inFile, modelId)

    endTime = time.time()
    print('Cost %s seconds.' % (endTime - startTime))