from osgeo import gdal
from pyhdf.SD import SD,SDC,SDS
import numpy as np
import os
def Model_6S_inputParams(mod03_file):
    '''
    获取6S模型参数
    @mod03_file: 用于提取区域内均值太阳高度角等信息
    @待裁剪shp_file {str}: 研究区域矢量文件
    @aerotype {int}: 气溶胶类型(默认大陆型)
    @altitude {float}: 海拔(km)
    @visibility {float}: 能见度(km)
    @band_need {list}: 所选波段, all表示默认全部处理
    '''
    hdf=SD(mod03_file,SDC.READ)
    Lat = hdf.select('Latitude').get()
    Lon = hdf.select('Longitude').get()
    Height=hdf.select('Height').get()
    SesZ=hdf.select('SensorZenith').get()
    SesA=hdf.select('SensorAzimuth').get()
    SolZ=hdf.select('SolarZenith').get()
    SolA=hdf.select('SolarAzimuth').get()
    #异常值处理
    #去除异常地域信息，经纬度异常值-999
    loc=np.where(Lat==-999)[0]#定位到异常行索引,ndarray
    #删除以后
    Lat_=np.delete(Lat,loc,axis=0)
    Lon_=np.delete(Lon,loc,axis=0)
    Height_=np.delete(Height,loc,axis=0)
    SesZ_=np.delete(SesZ,loc,axis=0)
    SesA_=np.abs(np.delete(SesA,loc,axis=0))
    SolZ_=np.delete(SolZ,loc,axis=0)
    SolA_=np.abs(np.delete(SolA,loc,axis=0))

    # 计算研究区域的平均天顶角和方位角
    sesz=np.mean(SesZ_)*0.01
    sesa=np.mean(SesA_)*0.01
    solz=np.mean(SolZ_)*0.01
    sola=np.mean(SolA_)*0.01
    lon=np.mean(Lon_)
    lat=np.mean(Lat_)
    altitude=0.05#km
    print('Height:',altitude)
    print(sesa,sesz,solz,sola)#遗留问题太阳方位角和卫星方位角为负值。。。

    #日期信息
    date_str = os.path.split(mod03_file)[1].split('.')[0]
    #year=int(date_str.split('_')[2])
    month=int(date_str.split('_')[3])
    day=int(date_str.split('_')[4])
    #hour=int(date_str.split('_')[5])
    #minute=int(date_str.split('_')[6])
    #date='%d/%d/%d %d:%d:00' % (year, month, day, hour, minute)
    visibility=40#km
    aero_type=3#城市气溶胶类型
    mtl_coef = {
                    'altitude': altitude,
                    'visibility': visibility,
                    'aero_type': aero_type,
                    'logitude': lon,
                    'latitude':lat,
                    'month': month,
                    'day': day,
                    'solz': solz,
                    'sola': sola,
                    'salz': sesz,
                    'sala': sesa
                }
    return mtl_coef