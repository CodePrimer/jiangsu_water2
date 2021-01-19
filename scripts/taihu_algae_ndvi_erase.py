# -*- coding: utf-8 -*-

"""太湖蓝藻编辑页面后端（点擦除，多边形擦除）"""

import os
import sys
import shutil
import time
import json

import osr
import gdal
import numpy as np

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from tools.isPointInPolygon import isPointInPolygon

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


class AlgaeTaihuNdviErase(object):

    def __init__(self):
        self.jsonPath = None  # 前后端通信json文件
        self.satellite = None  # 卫星名
        self.sensor = None  # 传感器名
        self.dataIdentify = None  # 数据源标识 卫星_传感器_分辨率
        self.res = None  # 结果文件像元分辨率（米）
        self.issue = None  # 期号

        self.baseName = None
        self.eraseIndex = None  # 擦除次数索引
        self.eraseType = None  # 擦除类型
        self.erasePoint = None  # 擦除点列表
        self.eraseRadius = None     # 擦除点半径
        self.eraseArea = None  # 擦除面顶点列表
        self.outputDir = None  # 当期产品输出文件夹路径
        self.ndviTifPath = None  # 植被指数结果路径
        self.algaeTifPath = ''  # 蓝藻产品结果路径（二值结果）
        self.intensityTifPath = ''  # 蓝藻强度文件结果
        self.eraseTempDir = ''      # 擦除临时文件
        self.jsonBeforePath = ''    # 擦除前json文件路径

        self.statistic = {}  # 蓝藻产品相关统计信息

    def doInit(self, jsonStr):
        jsonStr = jsonStr.replace('\\', '')
        inputParam = json.loads(jsonStr)

        jsonPath = inputParam['jsonPath']
        self.jsonPath = os.path.join(globalCfg['map_dir'], jsonPath).replace('\\', '/')
        self.outputDir = os.path.dirname(self.jsonPath)
        self.baseName = os.path.basename(self.jsonPath).replace('_ndvi.json', '')
        self.satellite = self.baseName.split('_')[0]
        self.sensor = self.baseName.split('_')[1]
        self.res = float(self.baseName.split('_')[4])
        self.issue = self.baseName.split('_')[3]
        self.dataIdentify = '_'.join([self.satellite, self.sensor, self.baseName.split('_')[4]]).upper()
        self.eraseIndex = inputParam['index']
        self.eraseType = inputParam['type']
        self.erasePoint = inputParam['latlng']
        self.eraseRadius = inputParam['radius']
        self.eraseArea = inputParam['area']
        self.ndviTifPath = os.path.join(self.outputDir, self.baseName + '_ndvi.org.tif')

    @staticmethod
    def algaeErasePolygon(inTifPath, outTifPath, polygon):
        """
        多边形擦除
        :param inTifPath: 擦除前蓝藻TIF文件
        :param outTifPath: 擦除后蓝藻TIF文件
        :param polygon: 擦除多边形集合 首尾点不相同
        :return:
        """

        ds = gdal.Open(inTifPath, gdal.GA_ReadOnly)
        width = ds.RasterXSize
        height = ds.RasterYSize
        algaeArray = ds.GetRasterBand(1).ReadAsArray()
        trans = ds.GetGeoTransform()
        proj = ds.GetProjection()
        ds = None

        polygon.append(polygon[0])  # 添加最初点，形成闭合面
        for i in range(width):
            for j in range(height):
                x = trans[0] + i * trans[1]
                y = trans[3] + j * trans[5]
                flag = isPointInPolygon([x, y], polygon)
                if flag:
                    algaeArray[j][i] = 0

        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(outTifPath, width, height, 1, gdal.GDT_Byte)
        outDs.SetGeoTransform(trans)
        outDs.SetProjection(proj)
        outDs.GetRasterBand(1).WriteArray(algaeArray)
        outDs = None

    @staticmethod
    def algaeErasePoint(inTifPath, outTifPath, point, radius):
        """
        点擦除
        :param inTifPath: 擦除前蓝藻TIF文件
        :param outTifPath: 擦除后蓝藻TIF文件
        :param point: 擦除点坐标
        :param radius: 擦出点半径 （单位 度）
        :return:
        """

        ds = gdal.Open(inTifPath, gdal.GA_ReadOnly)
        width = ds.RasterXSize
        height = ds.RasterYSize
        algaeArray = ds.GetRasterBand(1).ReadAsArray()
        trans = ds.GetGeoTransform()
        proj = ds.GetProjection()
        ds = None

        radiusM = float(radius) * 100000

        for i in range(width):
            for j in range(height):
                x = trans[0] + i * trans[1]
                y = trans[3] + j * trans[5]
                dist = ((x - point[0]) ** 2 + (y - point[1]) ** 2) ** 0.5
                if dist < radiusM:
                    algaeArray[j][i] = 0

        driver = gdal.GetDriverByName("GTiff")
        outDs = driver.Create(outTifPath, width, height, 1, gdal.GDT_Byte)
        outDs.SetGeoTransform(trans)
        outDs.SetProjection(proj)
        outDs.GetRasterBand(1).WriteArray(algaeArray)
        outDs = None

    @staticmethod
    def transformGeo2Proj(lonlat):
        """将经纬度转换为投影坐标"""
        prjStr = 'PROJCS["WGS_1984_UTM_Zone_51N",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",123],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]]]'
        prosrs = osr.SpatialReference()
        prosrs.ImportFromWkt(prjStr)
        geosrs = prosrs.CloneGeogCS()
        ct = osr.CoordinateTransformation(geosrs, prosrs)
        coords = ct.TransformPoint(lonlat[0], lonlat[1])
        return coords[:2]

    def prepare(self):
        self.eraseTempDir = os.path.join(os.path.dirname(self.jsonPath), 'erase_temp')
        if self.eraseIndex == 1:
            try:
                if os.path.isdir(self.eraseTempDir):
                    shutil.rmtree(self.eraseTempDir)
                    print('Delete erase_temp dir success.')
                os.makedirs(self.eraseTempDir)
                print('Create erase_temp dir success.')
                firstJson = self.jsonPath
                firstTif = self.jsonPath.replace('.json', '.tif')
                firstIns = self.jsonPath.replace('ndvi.json', 'intensity.tif')
                copyJsonPath = os.path.join(self.eraseTempDir, '0.json')
                copyTifPath = os.path.join(self.eraseTempDir, '0.tif')
                copyInsPath = os.path.join(self.eraseTempDir, '0_ins.tif')
                if os.path.exists(firstJson):
                    shutil.copyfile(firstJson, copyJsonPath)
                if os.path.exists(firstTif):
                    shutil.copyfile(firstTif, copyTifPath)
                if os.path.exists(firstIns):
                    shutil.copyfile(firstIns, copyInsPath)
            except Exception as e:
                print(e)
        else:
            pass

    def eraseAlgae(self):
        algaeBefore = os.path.join(self.eraseTempDir, str(int(self.eraseIndex) - 1) + '.tif')  # 擦除前蓝藻tif文件路径
        jsonBefore = os.path.join(self.eraseTempDir, str(int(self.eraseIndex) - 1) + '.json')  # 擦除前json文件路径
        self.jsonBeforePath = jsonBefore
        if not (os.path.exists(algaeBefore) and os.path.exists(jsonBefore)):
            print('Lost Before File, Erase Failed.')

        self.algaeTifPath = os.path.join(self.eraseTempDir, str(self.eraseIndex) + '.tif')  # 擦除后蓝藻tif保存路径

        if self.eraseType == 'point':
            # 点 经纬度转为utm坐标
            transPoint = AlgaeTaihuNdviErase.transformGeo2Proj([self.erasePoint['lng'], self.erasePoint['lat']])

            AlgaeTaihuNdviErase.algaeErasePoint(algaeBefore, self.algaeTifPath, transPoint, self.eraseRadius)
        elif self.eraseType == 'area':
            if isinstance(self.eraseArea, str):
                erasePolygon = eval(self.eraseArea)  # 前端传参为字符串
            else:
                erasePolygon = self.eraseArea
            transPolygon = []  # 多边形顶点 经纬度转为utm坐标
            for each in erasePolygon:
                transEach = AlgaeTaihuNdviErase.transformGeo2Proj([each[1], each[0]])
                transPolygon.append(transEach)
            AlgaeTaihuNdviErase.algaeErasePolygon(algaeBefore, self.algaeTifPath, transPolygon)
        else:
            pass

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

        self.intensityTifPath = os.path.join(self.eraseTempDir, str(self.eraseIndex) + '_ins.tif')
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

        # 之前json文件信息转储
        with open(self.jsonBeforePath, 'r') as fp:
            jsonBeforeInfo = json.load(fp)
        self.statistic['cloud'] = jsonBeforeInfo['cloud']
        self.statistic['algaeThreshold'] = jsonBeforeInfo['algaeThreshold']
        self.statistic['boundaryThreshold'] = jsonBeforeInfo['boundaryThreshold']
        self.statistic['lakeMask'] = jsonBeforeInfo['lakeMask']

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
        algaeProjPath = os.path.join(self.eraseTempDir, algaeProjName)
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
        outJsonPath = os.path.join(self.eraseTempDir, str(self.eraseIndex) + '.json')
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
    def main(inputStr):

        eraseObj = AlgaeTaihuNdviErase()
        eraseObj.doInit(inputStr)

        # 准备工作
        # 如果是第一次擦除，先创建temp文件夹，并复制首次tif和json文件到temp文件夹内，以0.tif、0.json保存。
        # 如果是第一次擦除，且发现已有temp文件夹，那就删除temp文件(某些暴力关闭会出现这种情况)
        eraseObj.prepare()

        # 进行蓝藻擦除
        eraseObj.eraseAlgae()

        # 生成蓝藻强度产品
        eraseObj.intensityProduct()

        # 蓝藻统计信息计算
        eraseObj.productStatistic()

        # 生成前端json文件
        eraseObj.toJson()


if __name__ == '__main__':

    # inputStr = '{"index":1,' \
    #            '"uuid":"d0b41b73-5a18-4361-9382-25b9fae7f541",' \
    #            '"type":"area",' \
    #            '"latlng":[],' \
    #            '"radius":"0",' \
    #            '"area":"[[31.28765057398494,120.01752124947741],[31.24888352022557,120.0133994147424],[31.237132784049958,120.07522693576755],[31.284126954630707,120.09308821961923]]",' \
    #            '"jsonPath":"model/output/6ce5de13-da13-11ea-871a-0242ac110003/20201111135158/TERRA_MODIS_L2_202011061115_250_00_00_taihu_algae_ndvi.json"}'

    inputStr = sys.argv[1]
    print(inputStr)
    startTime = time.time()
    AlgaeTaihuNdviErase.main(inputStr)
    endTime = time.time()
    print('Cost %s seconds.' % (endTime - startTime))
