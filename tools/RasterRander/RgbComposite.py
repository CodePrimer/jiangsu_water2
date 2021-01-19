# -*- coding: utf-8 -*-
"""
    多波段文件彩色合成工具类
    Input:
        1. inputPath : 输入文件路径 支持类型 [GeoTiff]
        2. bandComb : 彩色合成波段组合 (R,G,B)
    Param:
        1. noDataValue : 无效值 65535 默认为空
        2. stretchType : 拉伸方式  [None, 'LinearByte', 'LinearPercent']
        3. stretchParam : 拉伸参数列表 视不同拉伸方式而定
        3. returnMode : 返回类型 ['MEN', 'GEOTIFF', 'JPG', 'PNG']
        4. isAlpha : 是否将无效值设置透明 True/False 默认不透明
        5. outputPath : 输出文件路径 若returnMode为MEN则返回数组，其他将结果文件写入硬盘
    Output:

"""

import gdal
import numpy as np
from PIL import Image


class RgbComposite(object):

    def __init__(self):
        pass

    @staticmethod
    def LinearPercent(array, param, noDataValue=None):
        """
        百分比线性拉伸
        @param array: 被拉伸数组
        @param param: 拉伸参数列表 [percent]  percent:拉伸的百分比
        @param noDataValue: 不参与拉的值
        @return: 拉伸至byte型的单波段结果数组
        """
        if noDataValue:
            availLocation = array != noDataValue        # 有效值位置
        else:
            availLocation = np.ones((array.shape[0], array.shape[1]), dtype=np.bool_)

        bandMin = np.percentile(array[availLocation], param[0])
        bandMax = np.percentile(array[availLocation], 100 - param[0])
        # 将DN值归一化到0-255
        # 转换公式：y = (x - array_min)/(array_max - array_min) * (stretch_max - stretch_min) + stretch_min
        bandArrayByte = (array - bandMin) / (bandMax - bandMin) * (255 - 0) + 0
        bandArrayByte[bandArrayByte < 0] = 0
        bandArrayByte[bandArrayByte > 255] = 255
        bandArrayByte = bandArrayByte.astype(np.uint8)
        return bandArrayByte

    @staticmethod
    def Compose(inputPath, bandComb, noDataValue=None, stretchType='LinearPercent', stretchParam=[2], isAlpha=False,
                returnMode='MEM', outputPath=None, resize=None):
        """
        彩色合成主函数
        @param inputPath: str 输入GeoTIFF文件路径
        @param bandComb: list 彩色合成的波段组合 序号从1开始 (3, 2, 1)
        @param noDataValue: float 无效值，默认为None
        @param stretchType: str 拉伸方式名称
        @param stretchParam: list 拉伸参数
        @param isAlpha: boolean 是否将noData值设为透明
        @param returnMode: str 返回值类型
                           MEN-返回numpy数组
                           GEOTIFF-将GeoTiff格式文件写到硬盘 必须设置outputPath参数
                           JPG-将jgp格式文件写到硬盘 必须设置outputPath参数
                           PNG-将png格式文件写到硬盘 必须设置outputPath参数
        @param outputPath: str 输出文件路径
        @param resize: float 行列缩放系数，取值0-1  仅支持png,jpg
        @return: ndarray numpy类型数组
        """

        inDs = gdal.Open(inputPath)
        bands = inDs.RasterCount
        # rgb波段设置检验
        if len(bandComb) != 3 or max(bandComb) > bands:
            print('ERROR: Invalid band combination!')
            del inDs
            return None

        width = inDs.RasterXSize
        height = inDs.RasterYSize

        # 结果数组，预留alpha波段
        resultArray = np.zeros((height, width, 4), dtype=np.uint8)
        resultArray[:, :, 3] = 255

        # 如果设置无效值了，遍历三波段找到透明位置
        if noDataValue:
            for i in range(len(bandComb)):
                bandArray = inDs.GetRasterBand(bandComb[i]).ReadAsArray()
                resultArray[:, :, 3][bandArray == noDataValue] = 0

        # == 拉伸算法 ====================================================================== #
        if stretchType == 'LinearPercent':
            for i in range(len(bandComb)):
                bandArray = inDs.GetRasterBand(bandComb[i]).ReadAsArray()
                stretchArray = RgbComposite.LinearPercent(bandArray, stretchParam, noDataValue=noDataValue)
                resultArray[:, :, i] = stretchArray
        elif stretchType == '':
            pass
        else:
            pass

        # == 保存代码 ====================================================================== #
        if returnMode.upper() == 'GEOTIFF':
            proj = inDs.GetProjection()
            trans = inDs.GetGeoTransform()
            if isAlpha:
                writeBandNum = 4
            else:
                writeBandNum = 3
            outDriver = gdal.GetDriverByName("GTiff")
            outDs = outDriver.Create(outputPath, width, height, writeBandNum, gdal.GDT_Byte)
            outDs.SetProjection(proj)
            outDs.SetGeoTransform(trans)
            for i in range(writeBandNum):
                outDs.GetRasterBand(i + 1).WriteArray(resultArray[:, :, i])
            outDs = None
        elif returnMode.upper() == 'PNG':
            if isAlpha:
                imgObj = Image.fromarray(resultArray, mode='RGBA')
            else:
                imgObj = Image.fromarray(resultArray[:, :, 0:3], mode='RGB')
            if resize:
                imgObj = imgObj.resize((int(imgObj.width*resize), int(imgObj.height*resize)), Image.NEAREST)
            imgObj.save(outputPath)
        elif returnMode.upper() == 'JPG':
            if isAlpha:
                print('ERROR: Cannot set alpha band when save as JPG File.')
                return
            else:
                imgObj = Image.fromarray(resultArray[:, :, 0:3], mode='RGB')
            if resize:
                imgObj = imgObj.resize((int(imgObj.width*resize), int(imgObj.height*resize)), Image.NEAREST)
            imgObj.save(outputPath)
        elif returnMode.upper() == 'MEM':
            if isAlpha:
                imgObj = Image.fromarray(resultArray, mode='RGBA')
            else:
                imgObj = Image.fromarray(resultArray[:, :, 0:3], mode='RGB')
            if resize:
                imgObj = imgObj.resize((int(imgObj.width*resize), int(imgObj.height*resize)), Image.NEAREST)
            return np.asarray(imgObj)
        else:
            pass


if __name__ == '__main__':
    inFile = r'C:\Users\Administrator\Desktop\model\TERRA_MODIS_L2_202101141133_250_00_00_taihu_algae_ndvi.l2.tif'
    combine = [1, 2, 1]        # 波段组合
    noData = 65535         # 无效值
    outFile = r'C:\Users\Administrator\Desktop\model\TERRA_MODIS_L2_202101141133_250_00_00_taihu_algae_ndvi.l2_render.tif'   # 输出路径
    # resizeScale = 1       # 行列缩放系数
    abc = RgbComposite.Compose(inFile, combine, noDataValue=noData, returnMode='GEOTIFF', outputPath=outFile,
                               stretchParam=[0], isAlpha=True)
    print('Finish')
