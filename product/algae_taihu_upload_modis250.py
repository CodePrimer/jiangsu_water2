# -*- coding: utf-8 -*-

"""
上传数据接口后续自动调用产生产代码
"""

import os
import sys
import json

curPath = os.path.abspath(os.path.dirname(__file__))
projDir = os.path.split(curPath)[0]
sys.path.append(projDir)

from preprocess.preprocess_modis250_terra import mod02qkmToTif as terra_preprocess
from preprocess.preprocess_modis250_aqua import aqua_preprocess
from algae_taihu_modis250_auto import main as algae_product

globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)

if __name__ == '__main__':

    MOD02File = sys.argv[1]
    MOD03File = sys.argv[2]

    # MOD02File = r'C:\Users\Administrator\Desktop\temp\TERRA_X_2020_06_30_10_32_D_G.MOD02QKM.hdf'
    # MOD03File = r'C:\Users\Administrator\Desktop\temp\TERRA_X_2020_06_30_10_32_D_G.MOD03.hdf'

    # 调用预处理
    print('start preprocess modis data.')
    issue = ''.join(os.path.basename(MOD03File).split('_')[2:7]) + '00'
    processOutputName = 'TERRA_MODIS_250_L2_%s_061_00.tif' % issue
    processOutputPath = os.path.join(globalCfg['input_path'], 'satellite', 'EOS-MODIS-250', processOutputName)
    if os.path.exists(processOutputPath):
        os.remove(processOutputPath)
    if os.path.basename(MOD03File).split('_')[0] == 'TERRA':
        terra_preprocess(MOD02File, MOD03File, processOutputPath)
    elif os.path.basename(MOD03File).split('_')[0] == 'AQUA':
        aqua_preprocess(MOD02File, MOD03File, processOutputPath)
    else:
        pass

    # 调用产品
    if os.path.exists(processOutputPath):
        print('start generate algae product.')
        algae_product(processOutputPath)
