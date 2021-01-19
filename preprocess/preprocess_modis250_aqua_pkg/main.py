'''
处理程序：删除异常值，辐射定标、重投影、大气校正
'''
from .Re_Project import Reproject
from .Get_6S_params import Model_6S_inputParams
from .RemoveErro_and_RadCal import RemoveErro_and_RadCal
from .Atmos_6S_Corr import Atmos_6Scor
import os
import shutil
from osgeo import gdal
from pyhdf.SD import SD,SDC,SDS
import re
import numpy as np
gdal.UseExceptions()

def write_img(filename,im_proj,im_geotrans,im_data):
        #gdal数据类型包括
        #gdal.GDT_Byte,
        #gdal .GDT_UInt16, gdal.GDT_Int16, gdal.GDT_UInt32, gdal.GDT_Int32,
        #gdal.GDT_Float32, gdal.GDT_Float64
        #判断栅格数据的数据类型
        if 'int8' in im_data.dtype.name:
            datatype = gdal.GDT_Byte
        elif 'int16' in im_data.dtype.name:
            datatype = gdal.GDT_UInt16
        else:
            datatype = gdal.GDT_Float32

        #判读数组维数
        if len(im_data.shape) == 3:
            im_bands, im_height, im_width = im_data.shape
        else:
            im_bands, (im_height, im_width) = 1,im_data.shape 

        #创建文件
        driver = gdal.GetDriverByName("GTiff")            #数据类型必须有，因为要计算需要多大内存空间
        dataset = driver.Create(filename, im_width, im_height, im_bands, datatype)
        
        dataset.SetGeoTransform(im_geotrans)              #写入仿射变换参数
        dataset.SetProjection(im_proj)                    #写入投影

        if im_bands == 1:
            dataset.GetRasterBand(1).WriteArray(im_data)  #写入数组数据
        else:
            for i in range(im_bands):
                dataset.GetRasterBand(i+1).SetNoDataValue(-9999)
                dataset.GetRasterBand(i+1).WriteArray(im_data[i])

        del dataset

def main(mod_02_file,mod_03_file,path_6s,output_path):
    Fileout6s_dir=os.path.join(os.path.dirname(mod_02_file),'6STiff')
    if not os.path.exists(Fileout6s_dir):
        os.makedirs(Fileout6s_dir)
       
    # mtl_coef=Get_6S_params.Model_6S_inputParams(mod_03_file)#获取6S参数
    mtl_coef=Model_6S_inputParams(mod_03_file)#获取6S参数
    # mod_02_file_remove_Erro=RemoveErro_and_RadCal.RemoveErro_and_RadCal(mod_02_file)#去除异常值
    mod_02_file_remove_Erro=RemoveErro_and_RadCal(mod_02_file)#去除异常值
    # ds_0,ds_1=Re_Project.Reproject(mod_02_file_remove_Erro)#重投影
    ds_0,ds_1=Reproject(mod_02_file_remove_Erro)#重投影
    # temp0=Atmos_6S_Corr.Atmos_6Scor(mod_02_file_remove_Erro,ds_0,mtl_coef,path_6s,band=0)
    # temp1=Atmos_6S_Corr.Atmos_6Scor(mod_02_file_remove_Erro,ds_1,mtl_coef,path_6s,band=1)
    temp0=Atmos_6Scor(mod_02_file_remove_Erro,ds_0,mtl_coef,path_6s,band=0)
    temp1=Atmos_6Scor(mod_02_file_remove_Erro,ds_1,mtl_coef,path_6s,band=1)

    #波段合成，对于MOD02QKM
    width=ds_0.RasterXSize    #栅格矩阵的列数
    height=ds_0.RasterYSize   #栅格矩阵的行数
    geotrans=ds_0.GetGeoTransform()  #仿射矩阵
    proj=ds_0.GetProjection() #地图投影信息
    ds_0 = None
    ds_1 = None
    Atms_corr_data=np.ndarray(shape=[2,height,width])
    Atms_corr_data[0,:,:]=temp0
    Atms_corr_data[1,:,:]=temp1
    #大气校正 后文件写出
    # Atom_cor_band_Tif=os.path.join(Fileout6s_dir,os.path.basename(mod_02_file)[:-16])+'AllBand6S_Cor.tif'
    # write_img(Atom_cor_band_Tif,proj,geotrans,Atms_corr_data)

    write_img(output_path, proj, geotrans, Atms_corr_data)
    #叠加波段

    # 删除临时文件夹
    tempDir1 = os.path.join(os.path.dirname(mod_02_file), '6STiff')
    tempDir2 = os.path.join(os.path.dirname(mod_02_file), 'Rad_Cal_and_RemoveErro_hdf')
    if os.path.exists(tempDir1):
        shutil.rmtree(tempDir1)
    if os.path.exists(tempDir2):
        shutil.rmtree(tempDir2)


if __name__ == "__main__":

    path_6S=r'D:/Temp/6S/6S'
    hdf3=r'E:/1012/AQUA_X_2020_10_12_12_57_A_G.MOD03.hdf'
    hdf2=r"E:/1012/AQUA_X_2020_10_12_12_57_A_G.MOD02QKM.hdf"
    main(hdf2,hdf3,path_6S)
    print('Aqua卫星预处理结束！')