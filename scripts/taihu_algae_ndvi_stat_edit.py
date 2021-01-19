# -*- coding: utf-8 -*-

"""
湖区统计部分的编辑后台
各数据源编辑通用
"""

import os
import sys
import json

globalCfgPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../global_configure.json')
with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def main(jsonPath, lakeStat):

    with open(jsonPath, 'r') as fp:
        jsonData = json.load(fp)

    jsonData['lakeStat'] = lakeStat

    jsonText = json.dumps(jsonData)
    with open(jsonPath, "w", encoding='utf-8') as f:
        f.write(jsonText + "\n")


if __name__ == '__main__':

    # jsonStr = '{"jsonPath":"C:/Users/Administrator/Desktop/20201028142151/TERRA_MODIS_250_L2_20201028112100_061_00_taihu_algae_ndvi.json","lakeStat":{"zhushanhu":0,"meilianghu":0,"gonghu":0,"westCoast":0,"southCoast":0,"centerLake":0,"eastCoast":0,"eastTaihu":1}}'
    inputStr = sys.argv[1]
    print(type(inputStr))
    print(inputStr)
    inputStr = inputStr.replace('\\', '')
    inputParam = json.loads(inputStr)
    jsonPath = os.path.join(globalCfg['map_dir'], inputParam['jsonPath'])
    print(jsonPath)
    lakeStat = inputParam['lakeStat']
    print(lakeStat)
    main(jsonPath, lakeStat)

    print('Finish')






