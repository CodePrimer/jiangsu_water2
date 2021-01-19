# -*- coding: utf-8 -*-

"""太湖蓝藻编辑页面后端（云量，阈值，边界）"""

import os
import sys
import time
import json

import numpy as np
from osgeo import gdal, osr

# 湖区掩膜对应值
LAKE_MASK_DATA_DICT = {1: "zhushanhu", 2: "meilianghu", 3: "gonghu", 4: "westCoast", 5: "southCoast", 6: "centerLake",
                       7: "eastCoast", 8: "eastTaihu"}

# 行政区掩膜对应值
ADMIN_MASK_DATA_DICT = {1: 'wuxi', 2: 'changzhou', 3: 'suzhou'}

# 蓝藻强度分级ndvi切分百分比
ALGAE_INTENSITY_THRESHOLD = [0.2, 0.4]

globalCfgPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


class AlgaeTaihuNdviEdit(object):

    def __init__(self):
        self.jsonPath = None   # 前后端通信json文件
        self.satellite = None  # 卫星名
        self.sensor = None  # 传感器名
        self.dataIdentify = None  # 数据源标识 卫星_传感器_分辨率
        self.res = None  # 结果文件像元分辨率（米）
        self.issue = None  # 期号

        self.baseName = None
        self.algaeThreshold = None  # 蓝藻NDVI阈值
        self.boundaryThreshold = None  # 边界缩放信息
        self.lakeMask = None      # 湖区掩膜信息
        self.outputDir = None    # 当期产品输出文件夹路径
        self.ndviTifPath = None  # 植被指数结果路径
        self.algaeTifPath = ''  # 蓝藻产品结果路径（二值结果）
        self.intensityTifPath = ''  # 蓝藻强度文件结果
        self.cloud = None   # 外部传入云量

        self.statistic = {}  # 蓝藻产品相关统计信息

    def doInit(self, jsonStr):
        jsonStr = jsonStr.replace('\\', '')
        inputParam = json.loads(jsonStr)
        self.algaeThreshold = float(inputParam['algaeThreshold'])
        self.boundaryThreshold = int(inputParam['boundaryThreshold'])

        jsonPath = inputParam['jsonPath']
        self.jsonPath = os.path.join(globalCfg['map_dir'], jsonPath).replace('\\', '/')
        self.outputDir = os.path.dirname(self.jsonPath)
        self.baseName = os.path.basename(self.jsonPath).replace('_ndvi.json', '')
        self.satellite = self.baseName.split('_')[0]
        self.sensor = self.baseName.split('_')[1]
        self.res = float(self.baseName.split('_')[4])
        self.issue = self.baseName.split('_')[3]
        self.dataIdentify = '_'.join([self.satellite, self.sensor, self.baseName.split('_')[4]]).upper()
        self.lakeMask = inputParam['lakeMask']
        self.cloud = int(inputParam['cloud'])
        self.ndviTifPath = os.path.join(self.outputDir, self.baseName + '_ndvi.org.tif')
        if not os.path.exists(self.ndviTifPath):
            self.ndviTifPath = None

        # 初始化各参数检查
        checkList = [self.satellite, self.sensor, self.dataIdentify, self.res, self.issue, self.algaeThreshold,
                     self.boundaryThreshold, self.lakeMask, self.ndviTifPath]
        for each in checkList:
            if each is None:
                return False

    def algaeProduct(self):
        """蓝藻产品生产"""
        # 掩膜相关文件位置
        dependDir = os.path.join(globalCfg['depend_path'], 'taihu', str(int(self.res)))
        if not os.path.exists(dependDir):
            raise FileNotFoundError('Cannot Found Path: %s' % dependDir)

        boundaryMaskName = 'taihu_mask_utm[%d].tif' % self.boundaryThreshold
        boundaryMaskPath = os.path.join(dependDir, boundaryMaskName)     # 太湖边界掩膜TIF
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

        for v in LAKE_MASK_DATA_DICT.keys():
            if self.lakeMask[LAKE_MASK_DATA_DICT[v]]:
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
        algaeThreshold = self.algaeThreshold
        algaeArray[np.logical_and(ndviArray > algaeThreshold, boundaryBufferMaskArray == 1)] = 1

        algaeTifName = os.path.basename(self.ndviTifPath).replace('_ndvi.org.tif', '_ndvi.tif')
        self.algaeTifPath = os.path.join(self.outputDir, algaeTifName)
        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(self.algaeTifPath, width, height, 1, gdal.GDT_Byte)
        outDs.SetGeoTransform(trans)
        outDs.SetProjection(proj)
        outDs.GetRasterBand(1).WriteArray(algaeArray)
        outDs = None

        self.statistic['algaeThreshold'] = self.algaeThreshold
        self.statistic['boundaryThreshold'] = self.boundaryThreshold
        self.statistic['lakeMask'] = self.lakeMask
        self.statistic['cloud'] = self.cloud

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

        intensityTifName = os.path.basename(self.ndviTifPath).replace('_ndvi.org.tif', '_intensity.tif')
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

    @staticmethod
    def main(jsonStr):

        # 初始化
        editObj = AlgaeTaihuNdviEdit()
        editObj.doInit(jsonStr)

        # 生成蓝藻产品
        editObj.algaeProduct()

        # 生成蓝藻强度产品
        editObj.intensityProduct()

        # 蓝藻统计
        editObj.productStatistic()

        # 生成前端json
        editObj.toJson()


if __name__ == '__main__':

    # inputStr = '{"uuid":"bb786ed5-413c-409f-93ce-6d7a8bff3b51",' \
    #            '"cloud":30,' \
    #            '"algaeThreshold":0.1,' \
    #            '"boundaryThreshold":-3,' \
    #            '"lakeMask":{"zhushanhu":0,"meilianghu":0,"gonghu":0,"westCoast":0,"southCoast":0,"centerLake":0,"eastCoast":0,"eastTaihu":1},' \
    #            '"jsonPath":"model/output/6ce5de13-da13-11ea-871a-0242ac110003/20201111135158/TERRA_MODIS_L2_202011061115_250_00_00_taihu_algae_ndvi.json"}'

    # inputStr = '{"uuid":"2fd78fb8-5c8e-4cd9-8d5b-0a6ba29360c3","cloud":"96","algaeThreshold":0.1,"boundaryThreshold":0,"lakeMask":{"zhushanhu":0,"meilianghu":0,"gonghu":0,"westCoast":0,"southCoast":0,"centerLake":0,"eastCoast":0,"eastTaihu":1},"jsonPath":"model/output/6ce5de13-da13-11ea-871a-0242ac110003/20201119105949/AQUA_MODIS_250_L2_20201118131500_061_00_taihu_algae_ndvi.json"}'

    inputStr = sys.argv[1]
    print(type(inputStr))
    print(inputStr)
    startTime = time.time()
    AlgaeTaihuNdviEdit.main(inputStr)
    endTime = time.time()
    print('Cost %s seconds.' % (endTime - startTime))
