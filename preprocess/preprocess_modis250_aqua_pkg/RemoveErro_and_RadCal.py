import os
from pyhdf.SD import SD,SDC,SDS

import numpy as np
def RemoveErro_and_RadCal(Hdfname_in):
    '''
    @异常处理与辐射定标
    '''
    filedir=os.path.dirname(Hdfname_in)
    hdf=SD(Hdfname_in,SDC.READ)
    
    #经纬度信息层
    Lat = hdf.select('Latitude').get()
    Lon = hdf.select('Longitude').get()
    #去除异常地域信息，经纬度异常值-999
    loc=np.where(Lat==-999)[0]#定位到异常行索引,ndarray
    #删除以后
    Lat_=np.delete(Lat,loc,axis=0)
    Lon_=np.delete(Lon,loc,axis=0)
    #定标信息
    sds_obj = hdf.select('EV_250_RefSB')
    sds_info = sds_obj.attributes()
    scales = sds_info['radiance_scales']
    offsets = sds_info['radiance_offsets']
    #Aqua数据信息层,两波段
    Rad0=hdf.select('EV_250_RefSB').get()[0,:,:]
    Rad1=hdf.select('EV_250_RefSB').get()[1,:,:]
    
    # 辐射定标
    Rad0_cor=scales[0]*Rad0+offsets[0]
    Rad1_cor=scales[1]*Rad1+offsets[1]
    
    #数据信息层EV_250_RefSB，数据信息层剔除值索引为经纬度索引的4倍
    num_begin=0
    for i in range(Lat.shape[0]):
        if -999 in Lat[i,:]:
            num_begin=num_begin+1
            continue
        else:
            break
    num_end=0
    for j in range(i,Lat.shape[0]):
        if -999 in Lat[j,:]:
            num_end=num_end+1
    num_begin_=range(0,num_begin*4)
    num_end_=range((Lat.shape[0]-num_end)*4,Lat.shape[0]*4)

    #辐射定标后——删除异常
    #第一波段
    Rad0_cor_=np.delete(Rad0_cor,num_begin_,axis=0)
    Rad0_cor__=np.delete(Rad0_cor_,[i-num_begin*4 for i in num_end_],axis=0)
    #第二波段
    Rad1_cor_=np.delete(Rad1_cor,num_begin_,axis=0)
    Rad1_cor__=np.delete(Rad1_cor_,[i-num_begin*4 for i in num_end_],axis=0)

    #创建新的hdf数据,写入辐射定标后的数据
    fileout=os.path.join(filedir,'Rad_Cal_and_RemoveErro_hdf')
    if not os.path.exists(fileout):
        os.makedirs(fileout)

    Remove_hdf_path = os.path.join(fileout,os.path.basename(Hdfname_in)[:-4]+'RemoveErro.hdf')
    #不存在文件
    if os.path.exists(Remove_hdf_path):
        pass
    else:
        # 创建输出hdf对象
        New_sd = SD(Remove_hdf_path, SDC.CREATE | SDC.WRITE)
        # 创建hdf中数据集create
        cur_sd_obj = New_sd.create('EV_250_RefSB_b1', SDC.FLOAT64, (Rad0_cor__.shape[0], Rad0_cor__.shape[1]))
        cur_sd_obj.set(Rad0_cor__)
        cur_sd_obj = New_sd.create('EV_250_RefSB_b2', SDC.FLOAT64, (Rad1_cor__.shape[0], Rad1_cor__.shape[1]))
        cur_sd_obj.set(Rad1_cor__)
        cur_sd_obj = New_sd.create('Latitude', SDC.FLOAT32, (Lat_.shape[0], Lat_.shape[1]))
        cur_sd_obj.set(Lat_)
        cur_sd_obj = New_sd.create('Longitude', SDC.FLOAT32, (Lon_.shape[0], Lon_.shape[1]))
        cur_sd_obj.set(Lon_)

        cur_sd_obj.endaccess()
        New_sd.end()
        hdf.end()
    return Remove_hdf_path