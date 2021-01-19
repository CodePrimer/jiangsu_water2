# -*- coding: utf-8 -*-

"""暂时不用"""
import gdal
import osr


def getTargetDsPath(hdfPath, targetName):
    ds = gdal.Open(hdfPath)
    subDs = ds.GetSubDatasets()  # 获取hdf中的子数据集

    # 找到目标数据集
    targetDsPath = ''
    for each in subDs:
        if targetName in each[0]:
            targetDsPath = each[0]
            break
    if not targetDsPath:
        print("未找到相应数据集")
    else:
        return targetDsPath


if __name__ == '__main__':
    inputFile = r'C:\Users\Administrator\Desktop\origion\TERRA_X_2020_10_12_11_21_D_G.MOD02QKM.hdf'

    # 子数据集
    subDsPath = getTargetDsPath(inputFile, 'MODIS_SWATH_Type_L1B:EV_250_RefSB')
    ds = gdal.Open(subDsPath)

    sr = osr.SpatialReference()
    sr.SetWellKnownGeogCS('WGS84')
    dsGCPs = ds.GetGCPs()
    newGCPs = ()
    for each in dsGCPs:
        print(each.GCPX)
        print(each.GCPY)
        print(each.GCPLine)
        print(each.GCPPixel)
        if each.GCPX != -999 and each.GCPY != -999:
            newGCPs = newGCPs + (each,)

    outTif = r'C:\Users\Administrator\Desktop\process\result.tif'
    width = ds.RasterXSize  # 输出文件列数
    height = ds.RasterYSize  # 输出文件列数
    bands = ds.RasterCount
    b1 = ds.GetRasterBand(1).ReadAsArray()
    b2 = ds.GetRasterBand(2).ReadAsArray()

    driver = gdal.GetDriverByName("GTiff")
    outDs = driver.Create(outTif, width, height, bands, gdal.GDT_UInt16)
    outDs.GetRasterBand(1).WriteArray(b1)
    outDs.GetRasterBand(2).WriteArray(b2)
    for each in newGCPs:
        outDs.SetGCPs(each, sr)
    gdal.Warp(outTif, ds, geoloc=True)
