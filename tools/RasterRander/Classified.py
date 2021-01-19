# -*- coding: utf-8 -*-
# @Author : wangbin
# @Time : 2020/8/18 20:07

"""
    单波段栅格进行分级渲染。将输入的单波段数据按照分级和颜色表输出为彩色图像。
    1.支持输出为带地理坐标的TIF格式，支持Alpha波段
    2.支持输出为不带地理坐标的图片格式(.png/.jpg)
    3.支持设置背景值颜色/支持设置透明值颜色(二者选一)
"""

import os

import gdal
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches


class Classified(object):
    """分级渲染类"""

    def __init__(self):
        pass

    @staticmethod
    def showColorBar(rgbList):
        rgbListNum = len(rgbList)
        start_y = 0
        rect_height = 1.0/rgbListNum
        fig, ax = plt.subplots(1)
        hexList = []
        for each in colorBar:
            hexList.append(Classified.RGB_list_to_Hex(each))
        for each in hexList:
            rect = patches.Rectangle((0, start_y), 0.2, rect_height, facecolor=each)
            start_y += rect_height
            ax.add_patch(rect)
        plt.show()

    @staticmethod
    def RGB_to_Hex(rgb):
        RGB = rgb.split(',')  # 将RGB格式划分开来
        color = '#'
        for i in RGB:
            num = int(i)
            # 将R、G、B分别转化为16进制拼接转换并大写  hex() 函数用于将10进制整数转换成16进制，以字符串形式表示
            color += str(hex(num))[-2:].replace('x', '0').upper()
        print(color)
        return color

    @staticmethod
    def RGB_list_to_Hex(RGB):
        # RGB = rgb.split(',')  # 将RGB格式划分开来
        color = '#'
        for i in RGB:
            num = int(i)
            # 将R、G、B分别转化为16进制拼接转换并大写  hex() 函数用于将10进制整数转换成16进制，以字符串形式表示
            color += str(hex(num))[-2:].replace('x', '0').upper()
        return color

    @staticmethod
    def Hex_to_RGB(HEX):
        r = int(HEX[1:3], 16)
        g = int(HEX[3:5], 16)
        b = int(HEX[5:7], 16)
        rgb = str(r) + ',' + str(g) + ',' + str(b)
        rgbTuple = (r, g, b)
        return rgbTuple

    @staticmethod
    # TODO 废除
    def CreateColorBar_backup(color_list, color_sum=100, returnMode='RGB'):
        """
        @param color_list: 渐变色颜色列表[起始色RGB, 中间色RGB, 中间色RGB, 终止色RGB]
        @param color_sum: 渐变色分级数量
        @param returnMode:
        @return:
        """
        color_center_count = len(color_list)

        color_sub_count = int(color_sum / (color_center_count - 1))
        color_index_start = 0
        color_map = []
        for color_index_end in range(1, color_center_count):
            color_rgb_start = color_list[color_index_start]
            color_rgb_end = color_list[color_index_end]
            # color_rgb_start = Hex_to_RGB(color_list[color_index_start])[1]
            # color_rgb_end = Hex_to_RGB(color_list[color_index_end])[1]
            r_step = (color_rgb_end[0] - color_rgb_start[0]) / color_sub_count
            g_step = (color_rgb_end[1] - color_rgb_start[1]) / color_sub_count
            b_step = (color_rgb_end[2] - color_rgb_start[2]) / color_sub_count

            now_color = color_rgb_start
            color_map.append(Classified.RGB_list_to_Hex(now_color))
            for color_index in range(1, color_sub_count):
                now_color = [now_color[0] + r_step, now_color[1] + g_step, now_color[2] + b_step]
                color_map.append(Classified.RGB_list_to_Hex(now_color))
                color_index_start = color_index_end

        returnList = []
        if returnMode == 'RGB':
            for each in color_map:
                rgb_tuple = Classified.Hex_to_RGB(each)
                returnList.append(rgb_tuple)
        else:
            for each in color_map:
                returnList.append(each)
        return returnList

    @staticmethod
    def CreateColorBar(color_list, color_sum=100):
        """
        @param color_list: 渐变色颜色列表[起始色RGB, 中间色RGB, 中间色RGB, 终止色RGB]
        @param color_sum: 渐变色分级数量
        @return:
        """
        colorListNum = len(color_list)
        colorSubSum = int(color_sum / (colorListNum - 1))
        colorMap = []
        for i in range(colorListNum-1):
            colorMapSub = []
            colorRgbStart = color_list[i]
            colorRgbEnd = color_list[i+1]
            r_step = (colorRgbEnd[0] - colorRgbStart[0]) / (colorSubSum - 1)
            g_step = (colorRgbEnd[1] - colorRgbStart[1]) / (colorSubSum - 1)
            b_step = (colorRgbEnd[2] - colorRgbStart[2]) / (colorSubSum - 1)

            colorMapSub.append(colorRgbStart)
            for j in range(colorSubSum - 1):
                nowColor = [colorRgbStart[0]+r_step*(j+1), colorRgbStart[1]+g_step*(j+1), colorRgbStart[2]+b_step*(j+1)]
                nowColorHex = Classified.RGB_list_to_Hex(nowColor)
                nowColorRGB = Classified.Hex_to_RGB(nowColorHex)
                colorMapSub.append(nowColorRGB)

            for each in colorMapSub:
                colorMap.append(each)

        return colorMap

    @staticmethod
    def Render(inputPath, colorTable, returnMode='MEM', isAlpha=False, outputPath=None, bgColor=(255, 255, 255)):
        """
        分级渲染主函数
        @param inputPath: str 输入GeoTIFF文件路径
        @param colorTable: dict: 分级渲染颜色表  {(minV, maxV): (R, G, B)}
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
            rgbaArray[:, :, 0][np.logical_and(array > each[0], array <= each[1])] = colorTable[each][0]
            rgbaArray[:, :, 1][np.logical_and(array > each[0], array <= each[1])] = colorTable[each][1]
            rgbaArray[:, :, 2][np.logical_and(array > each[0], array <= each[1])] = colorTable[each][2]
            # 将颜色表中出现过的数值像元值+1，最终0值像元为透明位置或背景色位置
            rgbaArray[:, :, 3][np.logical_and(array > each[0], array <= each[1])] += 1

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

    @staticmethod
    def Stretched(inputPath, valueRange, colorBar, returnMode='MEN', isAlpha=False, outputPath=None, bgColor=(255, 255, 255)):
        """
        拉伸渲染主函数
        @param inputPath: str 输入GeoTIFF文件路径
        @param valueRange: list: 拉伸值域范围 [拉伸最小值, 拉伸最大值]
        @param colorBar: list: 色度条RGB列表
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

        # 创建ColorTable
        colorBarNum = len(colorBar)
        valueStep = (float(valueRange[1]) - float(valueRange[0])) / (colorBarNum - 1)
        colorTable = {}
        for i in range(colorBarNum-1):
            startV = valueRange[0] + valueStep * i
            endV = valueRange[0] + valueStep * (i+1)
            colorTable[(startV, endV)] = colorBar[i]

        # 读取TIF数组
        inDs = gdal.Open(inputPath)
        width = inDs.RasterXSize
        height = inDs.RasterYSize
        array = inDs.GetRasterBand(1).ReadAsArray()

        # 创建空的rgba数组，预留alpha通道
        rgbaArray = np.zeros((height, width, 4), dtype=np.uint8)

        # 依次循环颜色表进行像元颜色填充
        for each in colorTable.keys():
            rgbaArray[:, :, 0][np.logical_and(array > each[0], array <= each[1])] = colorTable[each][0]
            rgbaArray[:, :, 1][np.logical_and(array > each[0], array <= each[1])] = colorTable[each][1]
            rgbaArray[:, :, 2][np.logical_and(array > each[0], array <= each[1])] = colorTable[each][2]
            # 将颜色表中出现过的数值像元值+1，最终0值像元为透明位置或背景色位置
            rgbaArray[:, :, 3][np.logical_and(array > each[0], array <= each[1])] += 1

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
    inputFile = r'C:\Users\Administrator\Desktop\model\output\621b37ac-ed93-11e9-b63f-0242ac110008\20201110181717\NPP_VIIRS_375_L2_20200630131800_001_00_taihu_algae_ndvi.org.tif'
    outputFile = r'C:\Users\Administrator\Desktop\model\output\621b37ac-ed93-11e9-b63f-0242ac110008\20201110181717\rgb1.tif'
    # colorInfo = {(-1, 0): (255, 255, 255),
    #              (0, 0.1): (255, 0, 0),
    #              (0.1, 0.2): (230, 0, 0),
    #              (0.2, 0.3): (210, 0, 0),
    #              (0.3, 0.4): (190, 0, 0)}  # 唯一值渲染颜色表
    # Classified.Render(inputFile, colorInfo, returnMode='GEOTIFF', outputPath=outputFile, isAlpha=False)

    colorList = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    colorBar = Classified.CreateColorBar(colorList, color_sum=300)
    # Classified.showColorBar(colorBar)
    Classified.Stretched(inputFile, [0, 1], colorBar, returnMode='GEOTIFF', outputPath=outputFile, isAlpha=False)

    print('Finish')

