# -*- coding: utf-8 -*-

"""
modis蓝藻报告相关文件生成代码
1.专题图
2.各类报告文字
3.更新切片
"""

import os
import sys
import json
import time


from osgeo import gdal
import skimage.io
import skimage.transform
from PIL import Image, ImageDraw, ImageFont
import numpy as np

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)  # 添加工程根目录到系统变量，方便后续导包

from tools.RasterRander.RgbComposite import RgbComposite
from tools.RasterRander.UniqueValues import UniqueValues

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')

with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def exportImage(jsonPath):
    """生成后续所需所有专题图"""
    tempDir = os.path.dirname(jsonPath)
    jsonBaseName = os.path.basename(jsonPath)

    # 1.出专题图
    # 专题图相关文件
    l2TifPath = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi.l2.tif'))  # 原始数据
    algaeTifPath = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi.tif'))  # 蓝藻产品
    intensityTifPath = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'intensity.tif'))  # 强度产品

    if not os.path.isfile(l2TifPath):
        print('Cannot Find %s' % l2TifPath)
        return
    if not os.path.isfile(algaeTifPath):
        print('Cannot Find %s' % algaeTifPath)
        return
    if not os.path.isfile(intensityTifPath):
        print('Cannot Find %s' % intensityTifPath)
        return

    # mxd数据框范围 (195203.762, 3420416.355, 280082.543, 3498433.803) utm_zone_51N
    # mxd数据框范围 (12284297.415195609, 3516083.924476728, 12369297.415195609, 3438583.924476728) Albers
    dataFrameBounds = (195203.762, 3420416.355, 280082.543, 3498433.803)

    # 相关文件以数据框进行放缩 TODO 取消写临时文件到硬盘
    l2ClipPath = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi.l2_tmp.tif'))
    algaeClipPath = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_tmp.tif'))
    intensityClipPath = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'intensity_tmp.tif'))
    if os.path.exists(l2ClipPath):
        os.remove(l2ClipPath)
    if os.path.exists(algaeClipPath):
        os.remove(algaeClipPath)
    if os.path.exists(intensityClipPath):
        os.remove(intensityClipPath)

    # 裁切到模板空间大小
    ds = gdal.Warp(l2ClipPath, l2TifPath, format='GTiff', outputBounds=dataFrameBounds, dstNodata=65535,
                   xRes=250, yRes=250)
    ds = None
    ds = gdal.Warp(algaeClipPath, algaeTifPath, format='GTiff', outputBounds=dataFrameBounds, dstNodata=0,
                   xRes=250, yRes=250)
    ds = None
    ds = gdal.Warp(intensityClipPath, intensityTifPath, format='GTiff', outputBounds=dataFrameBounds, dstNodata=0,
                   xRes=250, yRes=250)
    ds = None

    # 太湖蓝藻监测的模板有效嵌入信息：
    # 右下角终止列(2055) 右下角终止行(1893)
    activateWidth = 2004    # 有效列数 2004
    activateHeight = 1841   # 有效行数 1841
    offsetWidth = 52    # 左上角起始列
    offsetHeight = 53       # 左上角起始行

    # 运算三种模板所需的有效数据范围内rgb数组 1.假彩色 2.蓝藻二值 3.聚集强度
    # 假彩色
    falseColorRgb = RgbComposite.Compose(l2ClipPath, (1, 2, 1), noDataValue=65535, returnMode='MEM')
    falseColorImageObj = Image.fromarray(falseColorRgb, mode='RGB')
    falseColorImageObj = falseColorImageObj.resize((activateWidth, activateHeight), Image.NEAREST)
    falseColorRgbResize = np.asarray(falseColorImageObj)

    # 蓝藻rgb
    colorTable = {1: (229, 250, 5)}
    algaeRgb = np.copy(falseColorRgb)  # 拷贝背景数组
    algaeRender = UniqueValues.Render(algaeClipPath, colorTable, returnMode='MEM')
    invalidLoc = np.logical_and(algaeRender[:, :, 0] == 255, algaeRender[:, :, 1] == 255, algaeRender[:, :, 2] == 255)
    algaeRgb[:, :, 0][~invalidLoc] = algaeRender[:, :, 0][~invalidLoc]
    algaeRgb[:, :, 1][~invalidLoc] = algaeRender[:, :, 1][~invalidLoc]
    algaeRgb[:, :, 2][~invalidLoc] = algaeRender[:, :, 2][~invalidLoc]
    algaeRgbImageObj = Image.fromarray(algaeRgb, mode='RGB')
    algaeRgbImageObj = algaeRgbImageObj.resize((activateWidth, activateHeight), Image.NEAREST)
    algaeRgbResize = np.asarray(algaeRgbImageObj)

    # 聚集强度
    colorTable = {1: (0, 255, 102), 2: (255, 254, 0), 3: (255, 153, 0)}
    intensityRgb = np.copy(falseColorRgb)  # 拷贝背景数组
    intensityRender = UniqueValues.Render(intensityClipPath, colorTable, returnMode='MEM')
    invalidLoc = np.logical_and(intensityRender[:, :, 0] == 255, intensityRender[:, :, 1] == 255, intensityRender[:, :, 2] == 255)
    intensityRgb[:, :, 0][~invalidLoc] = intensityRender[:, :, 0][~invalidLoc]
    intensityRgb[:, :, 1][~invalidLoc] = intensityRender[:, :, 1][~invalidLoc]
    intensityRgb[:, :, 2][~invalidLoc] = intensityRender[:, :, 2][~invalidLoc]
    intensityRgbImageObj = Image.fromarray(intensityRgb, mode='RGB')
    intensityRgbImageObj = intensityRgbImageObj.resize((activateWidth, activateHeight), Image.NEAREST)
    intensityRgbResize = np.asarray(intensityRgbImageObj)

    # 循环出图 出图信息存储在字典中
    outImagePath1 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg1_noPoints.jpg'))
    outImagePath2 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg1.jpg'))
    outImagePath3 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg2_noPoints.jpg'))
    outImagePath4 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg2.jpg'))
    outImagePath5 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg3_noPoints.jpg'))
    outImagePath6 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg3.jpg'))
    mouldDependDir = os.path.join(globalCfg['depend_path'], 'taihu', 'mould')
    mouldPath1 = os.path.join(mouldDependDir, 'taihu_algae_mould1.png')
    mouldPath2 = os.path.join(mouldDependDir, 'taihu_algae_mould1_point.png')
    mouldPath3 = os.path.join(mouldDependDir, 'taihu_algae_mould2.png')
    mouldPath4 = os.path.join(mouldDependDir, 'taihu_algae_mould2_point.png')
    mouldPath5 = os.path.join(mouldDependDir, 'taihu_algae_mould3.png')
    mouldPath6 = os.path.join(mouldDependDir, 'taihu_algae_mould3_point.png')
    mouldDict = {
        'mould1': {'modulePath': mouldPath1, 'activateArray': falseColorRgbResize, 'outImagePath': outImagePath1},
        'mould2': {'modulePath': mouldPath2, 'activateArray': falseColorRgbResize, 'outImagePath': outImagePath2},
        'mould3': {'modulePath': mouldPath3, 'activateArray': algaeRgbResize, 'outImagePath': outImagePath3},
        'mould4': {'modulePath': mouldPath4, 'activateArray': algaeRgbResize, 'outImagePath': outImagePath4},
        'mould5': {'modulePath': mouldPath5, 'activateArray': intensityRgbResize, 'outImagePath': outImagePath5},
        'mould6': {'modulePath': mouldPath6, 'activateArray': intensityRgbResize, 'outImagePath': outImagePath6}
        }
    for each in mouldDict.keys():
        moduleArray = skimage.io.imread(mouldDict[each]['modulePath'])
        # 模板中的非透明位置
        alphaLocation = moduleArray[:, :, 3] != 0
        moduleArrayBackup = np.copy(moduleArray)  # 拷贝模板数组

        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 0] \
            = mouldDict[each]['activateArray'][:, :, 0]
        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 1] \
            = mouldDict[each]['activateArray'][:, :, 1]
        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 2] \
            = mouldDict[each]['activateArray'][:, :, 2]
        moduleArray[:, :, 0][alphaLocation] = moduleArrayBackup[:, :, 0][alphaLocation]
        moduleArray[:, :, 1][alphaLocation] = moduleArrayBackup[:, :, 1][alphaLocation]
        moduleArray[:, :, 2][alphaLocation] = moduleArrayBackup[:, :, 2][alphaLocation]

        outImagePath = mouldDict[each]['outImagePath']
        skimage.io.imsave(outImagePath, moduleArray[:, :, 0:3].astype(np.uint8))

        # 添加左下角水印
        fontPath = os.path.join(globalCfg['depend_path'], 'ttf', 'simhei.ttf')  # 字体
        font = ImageFont.truetype(fontPath, 50)
        # 水印文本
        issue = jsonBaseName.split('_')[3]
        textMark = '%d年%d月%d日%d时%d分 EOS/MODIS 1B' % \
                   (int(issue[0:4]), int(issue[4:6]), int(issue[6:8]), int(issue[8:10]), int(issue[10:12]))

        image = Image.open(outImagePath)
        draw = ImageDraw.Draw(image)
        text_location = [300, 1960]
        draw.text(text_location, textMark, font=font, fill="#000000", spacing=0, align='left')
        image.save(outImagePath, 'jpeg')

    # 卫星中心模板大小与以上模板不同
    activateWidth = 2004
    activateHeight = 1841
    offsetWidth = 52
    offsetHeight = 63

    # 假彩色
    falseColorRgb = RgbComposite.Compose(l2ClipPath, (1, 2, 1), noDataValue=65535, returnMode='MEM')
    falseColorImageObj = Image.fromarray(falseColorRgb, mode='RGB')
    falseColorImageObj = falseColorImageObj.resize((activateWidth, activateHeight), Image.NEAREST)
    falseColorRgbResize = np.asarray(falseColorImageObj)

    # 蓝藻rgb
    colorTable = {1: (229, 250, 5)}
    algaeRgb = np.copy(falseColorRgb)  # 拷贝背景数组
    algaeRender = UniqueValues.Render(algaeClipPath, colorTable, returnMode='MEM')
    invalidLoc = np.logical_and(algaeRender[:, :, 0] == 255, algaeRender[:, :, 1] == 255, algaeRender[:, :, 2] == 255)
    algaeRgb[:, :, 0][~invalidLoc] = algaeRender[:, :, 0][~invalidLoc]
    algaeRgb[:, :, 1][~invalidLoc] = algaeRender[:, :, 1][~invalidLoc]
    algaeRgb[:, :, 2][~invalidLoc] = algaeRender[:, :, 2][~invalidLoc]
    algaeRgbImageObj = Image.fromarray(algaeRgb, mode='RGB')
    algaeRgbImageObj = algaeRgbImageObj.resize((activateWidth, activateHeight), Image.NEAREST)
    algaeRgbResize = np.asarray(algaeRgbImageObj)

    # 聚集强度
    colorTable = {1: (0, 255, 102), 2: (255, 254, 0), 3: (255, 153, 0)}
    intensityRgb = np.copy(falseColorRgb)  # 拷贝背景数组
    intensityRender = UniqueValues.Render(intensityClipPath, colorTable, returnMode='MEM')
    invalidLoc = np.logical_and(intensityRender[:, :, 0] == 255, intensityRender[:, :, 1] == 255,
                                intensityRender[:, :, 2] == 255)
    intensityRgb[:, :, 0][~invalidLoc] = intensityRender[:, :, 0][~invalidLoc]
    intensityRgb[:, :, 1][~invalidLoc] = intensityRender[:, :, 1][~invalidLoc]
    intensityRgb[:, :, 2][~invalidLoc] = intensityRender[:, :, 2][~invalidLoc]
    intensityRgbImageObj = Image.fromarray(intensityRgb, mode='RGB')
    intensityRgbImageObj = intensityRgbImageObj.resize((activateWidth, activateHeight), Image.NEAREST)
    intensityRgbResize = np.asarray(intensityRgbImageObj)

    outImagePath7 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg1_wxzx.jpg'))
    outImagePath8 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg2_wxzx.jpg'))
    outImagePath9 = os.path.join(tempDir, jsonBaseName.replace('ndvi.json', 'ndvi_reportImg3_wxzx.jpg'))
    mouldPath7 = os.path.join(mouldDependDir, 'taihu_algae_mould1_wxzx.png')
    mouldPath8 = os.path.join(mouldDependDir, 'taihu_algae_mould2_wxzx.png')
    mouldPath9 = os.path.join(mouldDependDir, 'taihu_algae_mould3_wxzx.png')
    mouldDict = {
        'mould7': {'modulePath': mouldPath7, 'activateArray': falseColorRgbResize, 'outImagePath': outImagePath7},
        'mould8': {'modulePath': mouldPath8, 'activateArray': algaeRgbResize, 'outImagePath': outImagePath8},
        'mould9': {'modulePath': mouldPath9, 'activateArray': intensityRgbResize, 'outImagePath': outImagePath9}
    }

    for each in mouldDict.keys():
        moduleArray = skimage.io.imread(mouldDict[each]['modulePath'])
        # 模板中的非透明位置
        alphaLocation = moduleArray[:, :, 3] != 0
        moduleArrayBackup = np.copy(moduleArray)  # 拷贝模板数组

        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 0] \
            = mouldDict[each]['activateArray'][:, :, 0]
        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 1] \
            = mouldDict[each]['activateArray'][:, :, 1]
        moduleArray[offsetHeight:offsetHeight + activateHeight, offsetWidth:offsetWidth + activateWidth, 2] \
            = mouldDict[each]['activateArray'][:, :, 2]
        moduleArray[:, :, 0][alphaLocation] = moduleArrayBackup[:, :, 0][alphaLocation]
        moduleArray[:, :, 1][alphaLocation] = moduleArrayBackup[:, :, 1][alphaLocation]
        moduleArray[:, :, 2][alphaLocation] = moduleArrayBackup[:, :, 2][alphaLocation]

        outImagePath = mouldDict[each]['outImagePath']
        skimage.io.imsave(outImagePath, moduleArray[:, :, 0:3].astype(np.uint8))

        # 添加左下角水印
        fontPath = os.path.join(globalCfg['depend_path'], 'ttf', 'simhei.ttf')  # 字体
        font = ImageFont.truetype(fontPath, 50)
        # 水印文本
        issue = jsonBaseName.split('_')[3]
        textMark = '%d年%d月%d日%d时%d分 EOS/MODIS 1B' % \
                   (int(issue[0:4]), int(issue[4:6]), int(issue[6:8]), int(issue[8:10]), int(issue[10:12]))

        image = Image.open(outImagePath)
        draw = ImageDraw.Draw(image)
        text_location = [300, 1973]
        draw.text(text_location, textMark, font=font, fill="#000000", spacing=0, align='left')
        image.save(outImagePath, 'jpeg')

    # 删除临时文件
    if os.path.exists(l2ClipPath):
        os.remove(l2ClipPath)
    if os.path.exists(algaeClipPath):
        os.remove(algaeClipPath)
    if os.path.exists(intensityClipPath):
        os.remove(intensityClipPath)


if __name__ == '__main__':
    jsonPath = r'C:\Users\Administrator\Desktop\model\output\6ce5de13-da13-11ea-871a-0242ac110003\20201112132011\TERRA_MODIS_L2_202006301032_250_00_00_taihu_algae_ndvi.json'
    startTime = time.time()
    exportImage(jsonPath)
    endTime = time.time()
    print('Cost %s seconds.' % (endTime - startTime))
