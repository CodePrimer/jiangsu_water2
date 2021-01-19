# -*- coding: utf-8 -*-
# @Author : wangbin
# @Time : 2020/8/15 11:52

"""
    单波段栅格进行唯一值渲染。将输入的单波段数据按照颜色表输出为彩色图像。
    1.支持输出为带地理坐标的TIF格式，支持Alpha波段
    2.支持输出为不带地理坐标的图片格式(.png/.jpg)
    3.支持设置背景值颜色/支持设置透明值颜色(二者选一)

"""

import gdal
import numpy as np
from PIL import Image


class UniqueValues(object):
    """唯一值渲染类"""

    def __init__(self):
        pass

    @staticmethod
    def Render(inputPath, colorTable, returnMode='MEM', isAlpha=False, outputPath=None, bgColor=(255, 255, 255)):
        """
        唯一值渲染主函数
        @param inputPath: str 输入GeoTIFF文件路径
        @param colorTable: dict: 分级渲染颜色表  {value: (R, G, B)}
        @param returnMode: str 返回值类型
                           MEN-返回numpy数组
                           GEOTIFF-将GeoTiff格式文件写到硬盘 必须设置outputPath参数
                           JPG-将jgp格式文件写到硬盘 必须设置outputPath参数
                           PNG-将png格式文件写到硬盘 必须设置outputPath参数
        @param isAlpha: boolean 是否将颜色表以外的值设为透明
        @param outputPath: str 输出文件路径
        @param bgColor: 背景值颜色，默认白色
        @return:
        """
        # 读取TIF数组
        inDs = gdal.Open(inputPath)
        width = inDs.RasterXSize
        height = inDs.RasterYSize
        array = inDs.GetRasterBand(1).ReadAsArray()

        # 创建空的rgba数组，预留alpha通道
        rgbaArray = np.zeros((height, width, 4), dtype=np.uint8)

        # 依次循环颜色表进行像元颜色填充
        for each in colorTable.keys():
            rgbaArray[:, :, 0][array == each] = colorTable[each][0]
            rgbaArray[:, :, 1][array == each] = colorTable[each][1]
            rgbaArray[:, :, 2][array == each] = colorTable[each][2]
            rgbaArray[:, :, 3][array == each] += 1  # 将颜色表中出现过的数值像元值+1，最终0值像元为透明位置或背景色位置

        # 其他值填充背景色
        rgbaArray[:, :, 0][rgbaArray[:, :, 3] == 0] = bgColor[0]
        rgbaArray[:, :, 1][rgbaArray[:, :, 3] == 0] = bgColor[1]
        rgbaArray[:, :, 2][rgbaArray[:, :, 3] == 0] = bgColor[2]
        # 颜色表中的值设置不透明
        rgbaArray[:, :, 3][rgbaArray[:, :, 3] != 0] = 255  # 有值区域透明设为255（不透明）

        # == 保存代码 ======================================================================
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
                outDs.GetRasterBand(i + 1).WriteArray(rgbaArray[:, :, i])
            outDs = None
        elif returnMode.upper() == 'PNG':
            if isAlpha:
                imgObj = Image.fromarray(rgbaArray, mode='RGBA')
            else:
                imgObj = Image.fromarray(rgbaArray[:, :, 0:3], mode='RGB')
            imgObj.save(outputPath)
        elif returnMode.upper() == 'JPG':
            if isAlpha:
                print('ERROR: Cannot set alpha band when save as JPG File.')
                return
            else:
                imgObj = Image.fromarray(rgbaArray[:, :, 0:3], mode='RGB')
            imgObj.save(outputPath)
        elif returnMode.upper() == 'MEM':
            if isAlpha:
                imgObj = Image.fromarray(rgbaArray, mode='RGBA')
            else:
                imgObj = Image.fromarray(rgbaArray[:, :, 0:3], mode='RGB')
            return np.asarray(imgObj)
        else:
            pass


if __name__ == '__main__':

    inputFile = r'C:\Users\Administrator\Desktop\model\output\6ce5de13-da13-11ea-871a-0242ac110003\20201112132011\TERRA_MODIS_L2_202006301032_250_00_00_taihu_algae_intensity_tmp.tif'
    outputFile = r'C:\Users\Administrator\Desktop\model\output\6ce5de13-da13-11ea-871a-0242ac110003\20201112132011\a.png'
    colTable = colorTable = {1: (0, 255, 102), 2: (255, 255, 0), 3: (255, 153, 0)}
    UniqueValues.Render(inputFile, colTable, returnMode='png', outputPath=outputFile, isAlpha=False)