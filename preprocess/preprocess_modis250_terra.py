# -*- coding: utf-8 -*-

"""星地通FTP推送的Terra数据预处理"""

import os
import sys
import re
import time
import json

import gdal
import numpy as np


globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def getMetadata(hdfPath, subDsName, paramList):
    """
    从hdf文件的指定dataset中获取指定元数据
    :param hdfPath: hdf文件路径
    :param subDsName: 子数据集名称    e.g: MODIS_SWATH_Type_L1B:EV_250_RefSB
    :param paramList: 需要获取的参数列表
    :return: dict
    """

    ds = gdal.Open(hdfPath)
    subDs = ds.GetSubDatasets()     # 获取hdf中的子数据集

    # 找到目标数据集
    targetDsPath = ''
    for each in subDs:
        if subDsName in each[0]:
            targetDsPath = each[0]
            break
    if not targetDsPath:
        print("未找到相应数据集")
    targetDs = gdal.Open(targetDsPath)

    # 从元数据中获取信息
    targetDsMetadata = targetDs.GetMetadata()
    resultDict = {}
    for key, value in targetDsMetadata.items():
        if key in paramList:
            resultDict[key] = value
    ds = None
    targetDs = None
    return resultDict


def hegTools(inHdfFile, outTifPath, objectName, fieldName, bandNumber):
    """
    使用hegTools将hdf中某个子数据集的某个波段转换为TIF格式
    :param inHdfFile: 输入hdf文件路径
    :param outTifPath: 输出TIF路径
    :param objectName: 子数据集名称   e.g: 'MODIS_SWATH_Type_L1B'
    :param fieldName: 数据字段名称    e.g: 'EV_250_RefSB'
    :param bandNumber: 波段数      e.g: 1
    :return:
    """

    # HEG相关环境变量
    HEG_DATA_PATH = globalCfg['HEG_DATA_PATH']
    HEG_PGSHOME_PATH = globalCfg['HEG_PGSHOME_PATH']
    HEG_MRTBINDIR_PATH = globalCfg['HEG_MRTBINDIR_PATH']

    os.environ['MRTDATADIR'] = HEG_DATA_PATH
    os.environ['PGSHOME'] = HEG_PGSHOME_PATH
    os.environ['MRTBINDIR'] = HEG_MRTBINDIR_PATH

    workspace = os.path.dirname(inHdfFile)
    hegBin = os.path.join(HEG_MRTBINDIR_PATH, 'hegtool')       # hegtool工具路径
    os.system('cd %s && %s -h %s > heg.log' % (workspace, hegBin, inHdfFile))
    hdfInfoFile = os.path.join(workspace, 'HegHdr.hdr')     # 当前输入hdf相关信息文件
    if not(os.path.exists(hdfInfoFile)):
        print('获取hdf文件信息出错：%s' % inHdfFile)

    latMin = None       # 原始数据最小经度
    latMax = None       # 原始数据最大经度
    lonMin = None       # 原始数据最小纬度
    lonMax = None       # 原始数据最大纬度
    xRes = None         # x向分辨率
    yRes = None         # y向分辨率
    with open(hdfInfoFile, 'r') as fp:
        lines = fp.readlines()
        for line in lines:
            if 'SWATH_LAT_MIN' in line:
                latMin = float(re.findall(r'[\d.]+', line)[0])
            elif 'SWATH_LAT_MAX' in line:
                latMax = float(re.findall(r'[\d.]+', line)[0])
            elif 'SWATH_LON_MIN' in line:
                lonMin = float(re.findall(r'[\d.]+', line)[0])
            elif 'SWATH_LON_MAX' in line:
                lonMax = float(re.findall(r'[\d.]+', line)[0])
            elif 'SWATH_X_PIXEL_RES_DEGREES' in line:
                xRes = float(re.findall(r'[\d.]+', line)[0])
            elif 'SWATH_Y_PIXEL_RES_DEGREES' in line:
                yRes = float(re.findall(r'[\d.]+', line)[0])
    if not (latMin and latMax and lonMin and lonMax and xRes and yRes):
        print('获取hdf文件信息出错')

    prmFile = os.path.join(workspace, 'HegSwath.prm')
    hegOutName = os.path.basename(outTifPath).split('.')[0] + '_heg.tif'
    hegOutPath = os.path.join(os.path.dirname(outTifPath), hegOutName)
    with open(prmFile, 'wb') as fp:
        fp.write(b'\nNUM_RUNS = 1\n\n')
        fp.write(b'BEGIN\n')
        fp.write(bytes('INPUT_FILENAME = %s\n' % inHdfFile, 'utf-8'))
        # fp.write(b'OBJECT_NAME = MODIS_SWATH_Type_L1B\n')
        # fp.write(b'FIELD_NAME = EV_250_RefSB|\n')
        fp.write(bytes('OBJECT_NAME = %s\n' % objectName, 'utf-8'))
        fp.write(bytes('FIELD_NAME = %s|\n' % fieldName, 'utf-8'))
        fp.write(bytes('BAND_NUMBER = %d\n' % bandNumber, 'utf-8'))
        fp.write(bytes('OUTPUT_PIXEL_SIZE_X = %f\n' % xRes, 'utf-8'))
        fp.write(bytes('OUTPUT_PIXEL_SIZE_Y = %f\n' % yRes, 'utf-8'))
        fp.write(bytes('SPATIAL_SUBSET_UL_CORNER = ( %f %f )\n' % (latMax, lonMin), 'utf-8'))
        fp.write(bytes('SPATIAL_SUBSET_LR_CORNER = ( %f %f )\n' % (latMin, lonMax), 'utf-8'))
        fp.write(b'RESAMPLING_TYPE = NN\n')
        fp.write(b'OUTPUT_PROJECTION_TYPE = GEO\n')
        fp.write(b'ELLIPSOID_CODE = DEFAULT\n')
        # fp.write(b'OUTPUT_PROJECTION_PARAMETERS = (0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0)\n')
        fp.write(bytes('OUTPUT_FILENAME = %s\n' % hegOutPath, 'utf-8'))
        fp.write(b'OUTPUT_TYPE = GEO\n')
        fp.write(b'END\n\n')
    swtifBin = os.path.join(HEG_MRTBINDIR_PATH, 'swtif')
    os.system('cd %s && %s -P HegSwath.prm > heg.log' % (workspace, swtifBin))

    # hegTiff转为geoTiff
    ds = gdal.Open(hegOutPath, gdal.GA_ReadOnly)
    width = ds.RasterXSize  # 输出文件列数
    height = ds.RasterYSize  # 输出文件行数
    bands = ds.RasterCount
    proj = ds.GetProjection()  # 输出文件投影
    geoTrans = ds.GetGeoTransform()  # 输出文件仿射矩阵
    xRes = abs(ds.GetGeoTransform()[1])  # 输出文件x向分辨率
    yRes = abs(ds.GetGeoTransform()[5])  # 输出文件y向分辨率
    dtypeDict = {"uint8": gdal.GDT_Byte, "int16": gdal.GDT_Int16, "int32": gdal.GDT_Int32, "uint16": gdal.GDT_UInt16,
                 "uint32": gdal.GDT_UInt32, "float32": gdal.GDT_Float32, "float64": gdal.GDT_Float64}
    dtype = dtypeDict[str(ds.GetRasterBand(1).ReadAsArray(0, 0, 1, 1).dtype)]
    data = ds.GetRasterBand(1).ReadAsArray()
    ds = None

    driver = gdal.GetDriverByName("GTiff")
    outDs = driver.Create(outTifPath, width, height, bands, dtype)
    outDs.SetGeoTransform(geoTrans)
    outDs.SetProjection(proj)
    outDs.GetRasterBand(1).WriteArray(data)
    outDs = None

    # 删除临时文件
    delNameList = ['heg.log', 'HegHdr.hdr', 'HegSwath.prm', 'hegtool.log', 'swtif.log', hegOutName, hegOutName + '.met']
    for each in delNameList:
        if os.path.exists(os.path.join(workspace, each)):
            os.remove(os.path.join(workspace, each))


def getSixsParams(mm, dd, SolarZenith, SolarAzimuth, SatelliteZenith, SatelliteAzimuth, wave):
    igeom = '0\n'
    asol = str(SolarZenith) + '\n'
    phio = str(SolarAzimuth) + '\n'
    avis = str(SatelliteZenith) + '\n'
    phiv = str(SatelliteAzimuth) + '\n'
    month = str(mm) + '\n'
    jday = str(dd) + '\n'
    if 4 < mm < 9:  # TODO 未进行地理位置判断
        idatm = '2\n'
    else:
        idatm = '3\n'
    iaer = '3\n'  # TODO 默认城市型
    v = '40\n'  # 默认能见度为40km 与FLASSH模型一致
    xps = '0.05\n'  # TODO 默认固定海拔
    xpp = '-1000\n'
    iwave = '-2\n'
    wlinf = str(wave[0]) + '\n'
    wlsup = str(wave[1]) + '\n'
    inhome = '0\n'
    idirect = '0\n'
    igroun = '1\n'
    rapp = '0\n'
    file_content = [igeom, asol, phio, avis, phiv, month, jday, idatm, iaer, v, xps, xpp, iwave, wlinf, wlsup,
                    inhome, idirect, igroun, rapp]
    sixs_exe_path = globalCfg['path_6s']
    in_txt = os.path.join(os.path.dirname(sixs_exe_path), 'in.txt')
    in_txt = in_txt.replace('\\', '/')
    with open(in_txt, 'w') as (f):
        f.writelines(file_content)
    out_txt = os.path.join(os.path.dirname(sixs_exe_path), 'sixs.out')
    out_txt = out_txt.replace('\\', '/')
    sixsDir = os.path.dirname(sixs_exe_path).replace('\\', '/')
    cmdStr1 = 'cd ' + sixsDir
    cmdStr2 = '6s.exe<in.txt>log'
    os.system(cmdStr1 + ' && ' + cmdStr2)
    time.sleep(1)
    with open(out_txt, 'r') as (f):
        for line in f.readlines():
            line = line.strip('\n')
            if 'coefficients xa xb xc' in line:
                coefAll = re.findall(r'[\.\d]+', line)
                xa = float(coefAll[0])
                xb = float(coefAll[1])
                xc = float(coefAll[2])
    return xa, xb, xc


def mod02qkmToTif(mod02Path, mod03Path, outputPath):
    """
    mod02qkm的hdf文件提取有效波段数据转为TIF文件
    :param mod02Path: mod02的hdf路径
    :param mod03Path: mod03的hdf路径
    :param outputPath: 输出tif路径
    :return:
    """
    fileBaseName = os.path.basename(mod02Path).replace('.hdf', '')
    tempDir = os.path.dirname(mod02Path)
    # RefSB数据集的band1和band2进行重投影转换
    dataTifPathList = []
    for i in range(2):
        tempFilePath = os.path.join(tempDir, fileBaseName + '_Band' + str(i + 1) + '.tif')
        hegTools(mod02Path, tempFilePath, 'MODIS_SWATH_Type_L1B', 'EV_250_RefSB', i + 1)
        dataTifPathList.append(tempFilePath)

    # 四个角度的重投影转换
    fileBaseName = os.path.basename(mod03Path).replace('.hdf', '')
    tempDir = os.path.dirname(mod03Path)
    # 创建字典存储转换后文件路径
    angleTifPathDict = {'SensorZenith': '', 'SensorAzimuth': '', 'SolarZenith': '', 'SolarAzimuth': ''}
    for key in angleTifPathDict.keys():
        tempFilePath = os.path.join(tempDir, fileBaseName + '_' + key + '.tif')
        hegTools(mod03Path, tempFilePath, 'MODIS_Swath_Type_GEO', key, 1)
        if os.path.exists(tempFilePath):
            angleTifPathDict[key] = tempFilePath

    # 辐射定标参数
    radianceParam = []
    MOD02MeteData = getMetadata(mod02Path, 'MODIS_SWATH_Type_L1B:EV_250_RefSB',
                                ['radiance_scales', 'radiance_offsets', '_FillValue'])
    radianceGain = [float(each) for each in MOD02MeteData['radiance_scales'].split(',')]
    radianceOffset = [float(each) for each in MOD02MeteData['radiance_offsets'].split(',')]
    for i in range(len(radianceGain)):
        gain = radianceGain[i]
        offset = radianceOffset[i]
        radianceParam.append((gain, offset))

    # 大气校正参数
    atmoParam = []
    # 计算太阳、卫星四个角度信息
    outBounds = (119.89189594793211, 30.928213636815027, 120.64137993381901, 31.548645232828754)    # 太湖区域

    angleValue = {'SensorZenith': '', 'SensorAzimuth': '', 'SolarZenith': '', 'SolarAzimuth': ''}
    angleNodataValue = -32767
    for key in angleTifPathDict.keys():
        # # 裁切研究区域
        tempFilePath = os.path.join(tempDir, fileBaseName + '_' + key + '_clip.tif')
        tempDs = gdal.Warp(tempFilePath, angleTifPathDict[key], format='GTiff', outputBounds=outBounds,
                           dstNodata=angleNodataValue)
        # tempDs = gdal.Open(angleTifPathDict[key], gdal.GA_ReadOnly)
        tempArray = tempDs.GetRasterBand(1).ReadAsArray().astype(np.float)
        tempArray[tempArray == angleNodataValue] = np.nan
        tempArray = tempArray * 0.01
        angleValue[key] = str(np.nanmean(tempArray))
        tempDs = None
        os.remove(tempFilePath)

    month = int(fileBaseName.split('_')[3])
    day = int(fileBaseName.split('_')[4])
    waveLength = [[0.62, 0.67], [0.841, 0.876]]  # band1和band的波长范围
    for each in waveLength:
        sixsResult = getSixsParams(month, day, angleValue['SolarZenith'], angleValue['SolarAzimuth'],
                                   angleValue['SensorZenith'], angleValue['SensorAzimuth'], each)
        print(sixsResult)
        atmoParam.append(sixsResult)

    # 先获取输出文件的相关信息
    tempDs = gdal.Open(dataTifPathList[0], gdal.GA_ReadOnly)
    outWidth = tempDs.RasterXSize  # 输出文件列数
    outHeight = tempDs.RasterYSize  # 输出文件行数
    outProj = tempDs.GetProjection()  # 输出文件投影
    outGeoTrans = tempDs.GetGeoTransform()  # 输出文件仿射矩阵
    outXRes = abs(tempDs.GetGeoTransform()[1])  # 输出文件x向分辨率
    outYRes = abs(tempDs.GetGeoTransform()[5])  # 输出文件y向分辨率
    tempDs = None

    # 创建结果文件
    driver = gdal.GetDriverByName("GTiff")
    outDs = driver.Create(outputPath, outWidth, outHeight, len(dataTifPathList), gdal.GDT_UInt16)
    outDs.SetGeoTransform(outGeoTrans)
    outDs.SetProjection(outProj)

    for i in range(len(dataTifPathList)):
        tempDs = gdal.Open(dataTifPathList[i], gdal.GA_ReadOnly)
        tempArray = tempDs.GetRasterBand(1).ReadAsArray()
        validRange = [0, 32767]  # 原始波段DN值的有效值范围
        nodataLoc = np.logical_or(tempArray < validRange[0], tempArray > validRange[1])
        # 辐射定标、大气校正计算
        tempArray = tempArray * radianceParam[i][0] + radianceParam[i][1]
        xa = atmoParam[i][0]
        xb = atmoParam[i][1]
        xc = atmoParam[i][2]
        tempArray = (xa * tempArray - xb) / (1 + xc * (xa * tempArray - xb)) * 10000
        tempArray[nodataLoc] = 65535
        outDs.GetRasterBand(i + 1).WriteArray(tempArray)
        tempDs = None
    outDs = None

    # 删除中间文件
    try:
        for each in dataTifPathList:
            if os.path.exists(each):
                os.remove(each)
        for key in angleTifPathDict.keys():
            if os.path.exists(angleTifPathDict[key]):
                os.remove(angleTifPathDict[key])
    except Exception as e:
        print(e)


if __name__ == '__main__':

    startTime = time.time()

    # mod02FilePath = r'C:\Users\Administrator\Desktop\hdf\TERRA_X_2020_12_03_10_56_D_G.MOD02QKM.hdf'
    # mod03FilePath = r'C:\Users\Administrator\Desktop\hdf\TERRA_X_2020_12_03_10_56_D_G.MOD03.hdf'
    #
    # outputFilePath = r'C:\Users\Administrator\Desktop\hdf\TERRA_MODIS_L2_202012031056_250_00_00.tif'

    mod02FilePath = sys.argv[1]
    mod03FilePath = sys.argv[2]
    outputFilePath = sys.argv[3]
    mod02qkmToTif(mod02FilePath, mod03FilePath, outputFilePath)

    endTime = time.time()
    print('Preprocess MODIS-250M Successful. Cost: %f' % (endTime - startTime))
