# -*- coding: utf-8 -*-

"""星地通FTP推送的Aqua数据预处理"""

import os
import sys
import json
import time

projectPath = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(projectPath)        # 添加工程根目录到系统变量，方便后续导包

from preprocess.preprocess_modis250_aqua_pkg.main import main

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def aqua_preprocess(mod02FilePath, mod03FilePath, outputFilePath):
    path_6s = os.path.dirname(globalCfg['path_6s'])
    main(mod02FilePath, mod03FilePath, path_6s, outputFilePath)


if __name__ == '__main__':

    startTime = time.time()

    # mod02FilePath = r'C:\Users\Administrator\Desktop\hdf\AQUA_X_2020_11_18_13_15_A_G.MOD02QKM.hdf'
    # mod03FilePath = r'C:\Users\Administrator\Desktop\hdf\AQUA_X_2020_11_18_13_15_A_G.MOD03.hdf'
    # outputFilePath = r'C:\Users\Administrator\Desktop\hdf\AQUA_MODIS_250_L2_20201118131500_061_00.tif'

    mod02FilePath = sys.argv[1]
    mod03FilePath = sys.argv[2]
    outputFilePath = sys.argv[3]

    aqua_preprocess(mod02FilePath, mod03FilePath, outputFilePath)

    endTime = time.time()
    print('Preprocess MODIS-250M Successful. Cost: %f' % (endTime - startTime))