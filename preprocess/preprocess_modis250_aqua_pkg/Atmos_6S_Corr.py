import os
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

def Atmos_6Scor(mod02_file,Dataset_in,mtl_coef,path_6s,band):
    '''
    @mod02_file: 辐射定标与异常值删除后的hdf数据
    @wave_index=i_band + 42 #对应MODIS在6s模型中对应的波段
    '''
    Fileout6s_dir=os.path.join(os.path.dirname(mod02_file),'6STiff')
    if not os.path.exists(Fileout6s_dir):
        os.makedirs(Fileout6s_dir)
    ds=Dataset_in
    if 'MOD02QKM' in mod02_file:
        nband=2
        im_width=ds.RasterXSize    #栅格矩阵的列数
        im_height=ds.RasterYSize   #栅格矩阵的行数
        im_geotrans=ds.GetGeoTransform()  #仿射矩阵
        im_proj=ds.GetProjection() #地图投影信息
            
        #6S大气校正,调用6S模型
        #wave_index=j+42
        # path_6s=r'D:/Temp/6S/6S'        # TODO delete

        with open(os.path.join(path_6s, 'in.txt'), 'w') as fp:
            # igeom
            fp.write('%d\n' % 0)
            # SOLZ SOLA THV PHV month day
            SOLZ = mtl_coef['solz']
            SOLA = mtl_coef['sola']
            PHV = mtl_coef['sala']
            THV = mtl_coef['salz']
            month = int(mtl_coef['month'])
            day = int(mtl_coef['day'])
            fp.write('%.2f\n %.2f\n %.2f\n %.2f\n %d\n %d\n' % (SOLZ, SOLA, THV, PHV, month, day))
            center_lat = mtl_coef['latitude']
            if center_lat<23.5 and month<9 and month>2:
                fp.write('%d\n' % 1)
            elif center_lat>=23.5 and center_lat<66.5 and month<9 and month>2:
                fp.write('%d\n' % 2)
            elif center_lat>=23.5 and center_lat<66.5 and (month>=9 or month<=2):
                fp.write('%d\n' % 3)
            elif center_lat>=66.5 and month<9 and month>2:
                fp.write('%d\n' % 4)
            elif center_lat>=66.5 and (month>=9 or month<=2):
                fp.write('%d\n' % 5)
            else:
                print('无法确定大气模型')
            fp.write('%d\n' % mtl_coef['aero_type'])
            #其他参数
            # 能见度
            fp.write('%.1f\n' % mtl_coef['visibility'])
            # 高程
            fp.write('%.3f\n' % mtl_coef['altitude'])
            # 传感器类型
            fp.write('%d\n' % -1000)#-1000星载传感器
            # 波段号
            wave_index=band+42
            fp.write('%d\n' % wave_index)
            # 其余参数
            fp.write('%d\n' % 0) # 无方向反射
            fp.write('%d\n' % 0) # 朗伯体假设
            fp.write('%d\n' % 4) # 湖泊水体
            fp.write('%d\n' % 0) # 进行大气校正
            fp.write('%.2f\n' % 0.01) # 默认反射率
            fp.write('%d\n' % 5) # 除了0,1,2外任意设置
        os.system('cd %s && 6S.exe <in.txt>log.txt'%path_6s)

        with open(os.path.join(path_6s, 'sixs.out'), 'r') as fp:
            for line in fp.readlines():
                if 'coefficients xa xb xc' in line:
                    coefAll = re.findall(r'[\.\d]+', line)
                    # y=xa*(measured radiance)-xb;  acr=y/(1.+xc*y)
                    xa=float(coefAll[0])
                    xb=float(coefAll[1])
                    xc=float(coefAll[2])
                    y=xa*(ds.GetRasterBand(1).ReadAsArray().astype(np.int))-xb
                    #print('y',y)
                    atms_corr_data=y/(1.0+xc*y)/3.14159
                    print('xa,xb,xc',xa,xb,xc)
                    print('daraset:',ds.GetRasterBand(1).ReadAsArray().shape)
                    print('y',y.shape)
                    print('单波段大气校正后：',atms_corr_data.shape)
                    break
        print('大气校正后：',atms_corr_data.shape)
        #大气校正 后文件写出
        atom_cor_band_Tif=os.path.join(Fileout6s_dir,os.path.basename(mod02_file)[:-4])+'6S_cor_Band'+str(band)+'.tif'     
        write_img(atom_cor_band_Tif,im_proj,im_geotrans,atms_corr_data)
        return(atms_corr_data)

