from osgeo import gdal
import os
#之前问题，重投影操作的是一个波段。。。尴尬
def Reproject(mod02_file):
    '''
    @mod02_file: 辐射定标与异常值删除后的hdf数据
    '''

    #重投影
    Fileout_dir=os.path.join(os.path.dirname(mod02_file),'ReprojectTiff')
    if not os.path.exists(Fileout_dir):
        os.makedirs(Fileout_dir)
    if 'MOD02QKM' in mod02_file:
        inHDFPath = 'HDF4_SDS:UNKNOWN:"%s":%d' %(mod02_file,0)#第一波段
        band_Tif_0=os.path.join(Fileout_dir,os.path.basename(mod02_file)[:-4])+'B'+str(0)+'.tif'
        ds_0=gdal.Warp(band_Tif_0,inHDFPath,format='GTiff', geoloc=True,dstSRS='EPSG:4326', resampleAlg=gdal.GRIORA_NearestNeighbour)
        inHDFPath1= 'HDF4_SDS:UNKNOWN:"%s":%d' %(mod02_file,1)#第2波段
        print(inHDFPath,inHDFPath1)
        band_Tif_1=os.path.join(Fileout_dir,os.path.basename(mod02_file)[:-4])+'B'+str(1)+'.tif'
        ds_1=gdal.Warp(band_Tif_1,inHDFPath1,format='GTiff', geoloc=True,dstSRS='EPSG:4326', resampleAlg=gdal.GRIORA_NearestNeighbour)
    return ds_0,ds_1

#mod_02_file=r'D:/Aqua/Rad_Cal_and_RemoveErro_hdf/AQUA_X_2020_08_21_13_21_A_G.MOD02QKMRemoveErro.hdf'
#Reproject(mod_02_file)