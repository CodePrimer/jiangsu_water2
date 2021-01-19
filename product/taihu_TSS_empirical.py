import os
import time
import json
import gdal
import numpy as np
import pymysql
import uuid
import sys
import shutil

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from tools.RasterRander.RgbComposite import RgbComposite
from tools.RasterRander.UniqueValues import UniqueValues
from tools.RasterRander.Classified import Classified

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)

TAIHU_BOUNDS = (195203.762, 3418022.181, 282703.762, 3505522.181)

def clipRegion(inPath, outPath):
    """输入数据转utm投影，并裁切研究区"""
    dependDir = globalCfg['depend_path']
    utmPrjFile = os.path.join(dependDir, 'prj', 'UTM_Zone_51N.prj')
    if not os.path.exists(utmPrjFile):
        raise FileNotFoundError('Cannot Found Path: %s' % utmPrjFile)
    gdal.Warp(outPath, inPath, dstSRS=utmPrjFile, format='GTiff', outputBounds=TAIHU_BOUNDS,
              dstNodata=65535, xRes=250, yRes=250)

def cloudProduct(inPath, outPath):
    """生成云产品"""
    ds = gdal.Open(inPath, gdal.GA_ReadOnly)
    width = ds.RasterXSize
    height = ds.RasterYSize
    redBandIndex = ds.GetRasterBand(1)
    bandR = redBandIndex.ReadAsArray()

    cloudArray = np.zeros((height, width), dtype=np.uint8)
    # 云检测阈值
    cloudArray[np.logical_and(bandR > 3500, bandR != 65535)] = 1

    driver = gdal.GetDriverByName("GTiff")
    outDs = driver.Create(outPath, width, height, 1, gdal.GDT_Byte)
    outDs.SetGeoTransform(ds.GetGeoTransform())
    outDs.SetProjection(ds.GetProjection())
    outDs.GetRasterBand(1).WriteArray(cloudArray)
    ds = None
    outDs = None

def tss(inPath,taihuPath,cloudPath, outPath):
    ds = gdal.Open(inPath, gdal.GA_ReadOnly)
    width = ds.RasterXSize
    height = ds.RasterYSize
    redBandIndex = ds.GetRasterBand(1)
    bandR = redBandIndex.ReadAsArray()
    bandR = bandR / 10000
    bandNir = ds.GetRasterBand(2).ReadAsArray()
    bandNir = bandNir / 10000
    tssArray = 9.65 * np.exp(58.81*bandR)
    tssArray=tssArray/1000
    tssArray=np.where(tssArray>150,tssArray*0.025+112.5,tssArray)
    tssArray[tssArray >200] = 200
    # 蓝藻掩膜
    algaeArray = (bandNir - bandR) / (bandNir + bandR)
    tssArray[algaeArray > 0] = 65535

    ds=None
    ds = gdal.Open(cloudPath, gdal.GA_ReadOnly)
    cloudArray = ds.GetRasterBand(1).ReadAsArray()
    tssArray[cloudArray==1]=65535
    ds = None
    ds = gdal.Open(taihuPath, gdal.GA_ReadOnly)
    bandArray = ds.GetRasterBand(1).ReadAsArray()
    tssArray[bandArray == 0] = 65535

    driver = gdal.GetDriverByName("GTiff")
    outDs = driver.Create(outPath, width, height, 1, gdal.GDT_Float32)
    outDs.SetGeoTransform(ds.GetGeoTransform())
    outDs.SetProjection(ds.GetProjection())
    outDs.GetRasterBand(1).WriteArray(tssArray)
    ds = None
    outDs = None
#假彩色合成rgb
def falseColor(inputPath,inputpath,outputDir):
    # inputPath是原影像，inputpath是裁剪后的影像
    basename = os.path.basename(inputPath).split('.')[0]
    falseColorTifName = basename + '_false_render.tif'
    falseColorTifPath = os.path.join(outputDir, falseColorTifName)
    RgbComposite.Compose(inputpath,(1,2,1),noDataValue=0,returnMode='GEOTIFF',\
                         outputPath=falseColorTifPath,stretchType='LinearPercent', \
                         stretchParam=[0], isAlpha=True)
    #rgb切片
    pythonPath = globalCfg['python_path']
    gdal2tilesPath = globalCfg['gdal2tiles_path']
    tileOutRootDir = globalCfg['tile_server_path']
    tileTif=falseColorTifPath
    tileName=basename + '_falseColor'
    tileOutDir=os.path.join(tileOutRootDir,tileName)
    if os.path.exists(tileOutDir):
        shutil.rmtree(tileOutDir)
    cmd = '%s %s -z %s -w all %s %s' % (pythonPath, gdal2tilesPath, '8-13', tileTif, tileOutDir)
    os.system(cmd)
    os.remove(tileTif)
#云产品合成rgb
def cloudColor(inputpath,inputpathcloud,outputDir):
    basename = os.path.basename(inputpath).split('.')[0]
    cloudColorTifName = os.path.basename(inputpath).replace('.tif', '_cloud.tif')
    cloudColorTifPath = os.path.join(outputDir, cloudColorTifName)
    colorTable = {1: (255, 255, 255)}
    UniqueValues.Render(inputpathcloud, colorTable, returnMode='GEOTIFF', outputPath=cloudColorTifPath, isAlpha=True)
   #云产品切片
    pythonPath = globalCfg['python_path']
    gdal2tilesPath = globalCfg['gdal2tiles_path']
    tileOutRootDir = globalCfg['tile_server_path']
    tileTif=cloudColorTifPath
    tileName=basename+'_cloud'
    tileOutDir=os.path.join(tileOutRootDir,tileName)
    if os.path.exists(tileOutDir):
        shutil.rmtree(tileOutDir)
    cmd = '%s %s -z %s -w all %s %s' % (pythonPath, gdal2tilesPath, '8-13', tileTif, tileOutDir)
    os.system(cmd)
    os.remove(tileTif)

def productColor(inputpath,inputpathProduct,outputDir):
    basename = os.path.basename(inputpath).split('.')[0]
    productColorTifName = basename + '_render.tif'
    productColorTifPath = os.path.join(outputDir, productColorTifName)
    colorList = [(0, 0, 255), (0, 255, 255), (0, 255, 0), (255, 215, 0), (255, 0, 0)]
    colorBar = Classified.CreateColorBar(colorList, color_sum=100)
    Classified.Stretched(inputpathProduct, [0,200], colorBar, returnMode='GEOTIFF', outputPath=productColorTifPath, isAlpha=True)

    pythonPath = globalCfg['python_path']
    gdal2tilesPath = globalCfg['gdal2tiles_path']
    tileOutRootDir = globalCfg['tile_server_path']
    tileTif = productColorTifPath
    tileName = basename
    tileOutDir = os.path.join(tileOutRootDir, tileName)
    if os.path.exists(tileOutDir):
        shutil.rmtree(tileOutDir)
    cmd = '%s %s -z %s -w all %s %s' % (pythonPath, gdal2tilesPath, '8-13', tileTif, tileOutDir)
    os.system(cmd)
    os.remove(tileTif)

def executeSql(modelUuid,tssTifPath):
    conn = pymysql.connect(
        db=globalCfg['database'],
        user=globalCfg['database_user'],
        password=globalCfg['database_passwd'],
        host=globalCfg['database_host'],
        port=globalCfg['database_port']
    )
    cursor = conn.cursor()
    chlaTifName = os.path.basename(tssTifPath)
    issue=chlaTifName.split('_')[3]
    sqlData = (modelUuid, chlaTifName)
    sqlStr='select * from '+ globalCfg['database_table_export_image'] + ' where model_uuid=%s and name=%s and is_deleted=0'
    cursor.execute(sqlStr, sqlData)
    sqlRes = cursor.fetchall()
    if len(sqlRes) > 0:
        print('already exist product.')
    else:
        image_uuid = str(uuid.uuid4())
        db_path = tssTifPath.replace('\\', '/').replace('/mnt/resource/', '')
        db_acquire_time = '%s-%s-%s %s:%s:%s' % \
                          (issue[0:4], issue[4:6], issue[6:8], issue[8:10], issue[10:12],'00')
        db_process_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        sqlStr='INSERT INTO '+globalCfg['database_table_export_image']+ \
               ' (uuid,name,path,type,model_type,satellite,sensor,lat_lr,lon_lr,lon_ul,lat_ul,' + \
               'acquire_time,cloud,area,process_time,is_deleted,model_uuid,colorbar_min,colorbar_max,' \
               'colorbar_tick,colorbar_color,unit,is_edit,is_edited,threshold) ' + \
               'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
        sqlData=(image_uuid,chlaTifName,db_path, 'tif','tss','AQUA','MODIS','30.8897','120.66946','119.8411','31.58009',\
                 db_acquire_time,0,0,db_process_time,0,modelUuid,0,200,'0,200','','mg/L',0,1,'')
        cursor.execute(sqlStr, sqlData)
        conn.commit()
        cursor.close()
        conn.close()

def main(inputPath,modelUuid):
    # 创建输出文件夹
    outputRootDir = globalCfg['output_path']
    timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    outputDir = os.path.join(outputRootDir, modelUuid, timeStamp)
    os.makedirs(outputDir)

    # 1.裁切研究区
    basename = os.path.basename(inputPath).split('.')[0]
    l2TifName = basename + '_taihu_tss_empir.l2.tif'
    l2TifPath = os.path.join(outputDir, l2TifName)
    clipRegion(inputPath, l2TifPath)

    # 2.云产品
    cloudTifName = basename + '_taihu_tss_empir.cloud.tif'
    cloudTifPath = os.path.join(outputDir, cloudTifName)
    cloudProduct(l2TifPath, cloudTifPath)

    # 3.计算产品
    tssTifName = basename + '_taihu_tss_empir.tif'
    dependDir = globalCfg['depend_path']
    taihuPath = os.path.join(dependDir, 'taihu', '250', 'taihu_mask_utm[0].tif')
    tssTifPath = os.path.join(outputDir, tssTifName)
    tss(l2TifPath, taihuPath, cloudTifPath, tssTifPath)

    # 4 RGB切片
    inputpath = l2TifPath
    falseColor(inputPath,inputpath, outputDir)
    # 5云产品切片
    inputPath = l2TifPath
    inputPathcloud = cloudTifPath
    # cloudColor(inputPath, inputPathcloud, outputDir)

    # 6 产品切片
    inputpath = l2TifPath
    inputpathProduct = tssTifPath
    productColor(inputpath, inputpathProduct, outputDir)

    # # 7 入库
    executeSql(modelUuid, tssTifPath)
if __name__ == '__main__':
    # 输入原始文件路径
    # inputPath = r"E:\SZ\20201214\model\input\satellite\EOS-MODIS-250\AQUA_MODIS_L2_202011111309_250_00_00.tif"
    # modelUuid = '07cd8ebf-ee2d-11e9-b63f-0242ac110008'
    # inputPath=r"E:\SZ\20201214\AQUA_MODIS_L2_202012201315_250_00_00.tif"
    # inputPath=r"E:\SZ\20201214\TERRA_MODIS_L2_202012201002_250_00_00.tif"
    inputPath = sys.argv[1]
    modelUuid = sys.argv[2]
    main(inputPath, modelUuid)