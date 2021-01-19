# -*- coding: utf-8 -*-
"""
    太湖蓝藻编辑页面 确定按钮"
    1.找到对应文件
    2.重命名
    3.打包
"""

import os
import sys
import json
import shutil


globalCfgDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
globalCfgPath = os.path.join(globalCfgDir, 'global_configure.json')

with open(globalCfgPath, 'r') as fp:
    globalCfg = json.load(fp)


def main(jsonPath):
    ensureDir = globalCfg['taihu_ensurefile']

    jsonBasename = os.path.basename(jsonPath)
    satelliteName = jsonBasename.split('_')[0]
    if satelliteName == 'TERRA':
        satelliteType = 'T'
    else:
        satelliteType = 'A'
    issue = jsonBasename.split('_')[3]
    copyDirName = issue[0:8] + satelliteType
    copyDir = os.path.join(ensureDir, copyDirName)
    if os.path.exists(copyDir):
        shutil.rmtree(copyDir)
    os.makedirs(copyDir)

    # 8个mxd文件 ==============================================================================
    mxdDir = os.path.join(globalCfg['depend_path'], 'taihu_algae_mxd')
    mxdList = os.listdir(mxdDir)
    for each in mxdList:
        mxdPath = os.path.join(mxdDir, each)
        mxdCopyName = each.replace('yyyyMMddX', issue[0:8] + satelliteType)
        mxdCopyPath = os.path.join(copyDir, mxdCopyName)
        shutil.copyfile(mxdPath, mxdCopyPath)

    # 11个jpg ==============================================================================
    jsonDir = os.path.dirname(jsonPath)
    jpgNameDict = {'_reportImg1.jpg': '太湖蓝藻水华分布1-%sPoint.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg2.jpg': '太湖蓝藻水华分布2-%sPoint.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg3.jpg': '太湖蓝藻水华分布3-%sPoint.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg1_noPoints.jpg': '太湖蓝藻水华分布1-%s.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg2_noPoints.jpg': '太湖蓝藻水华分布2-%s.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg3_noPoints.jpg': '太湖蓝藻水华分布3-%s.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg1_wxzx.jpg': '太湖蓝藻水华分布1-%s_部卫星中心专用.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg2_wxzx.jpg': '太湖蓝藻水华分布2-%s_部卫星中心专用.jpg' % (issue[0:8] + satelliteType),
                   '_reportImg3_wxzx.jpg': '太湖蓝藻水华分布3-%s_部卫星中心专用.jpg' % (issue[0:8] + satelliteType)}
    for key in jpgNameDict.keys():
        jpgPath = os.path.join(jsonDir, jsonBasename.replace('.json', key))
        jpgCopyPath = os.path.join(copyDir, jpgNameDict[key])
        if os.path.exists(jpgPath):
            if os.path.exists(jpgCopyPath):
                os.remove(jpgCopyPath)
            shutil.copyfile(jpgPath, jpgCopyPath)
        else:
            print('Cannot Find %s' % jpgPath)
        if key == '_reportImg1_noPoints.jpg':
            if os.path.exists(jpgPath):
                if os.path.exists(os.path.join(copyDir, '太湖蓝藻水华分布未会商1.jpg')):
                    os.remove(os.path.join(copyDir, '太湖蓝藻水华分布未会商1.jpg'))
                shutil.copyfile(jpgPath, os.path.join(copyDir, '太湖蓝藻水华分布未会商1.jpg'))
            else:
                print('Cannot Find %s' % jpgPath)
        if key == '_reportImg2.jpg':
            if os.path.exists(jpgPath):
                if os.path.exists(os.path.join(copyDir, '太湖蓝藻水华分布未会商1.jpg')):
                    os.remove(os.path.join(copyDir, '太湖蓝藻水华分布未会商1.jpg'))
                shutil.copyfile(jpgPath, os.path.join(copyDir, '太湖蓝藻水华分布未会商2Point.jpg'))
            else:
                print('Cannot Find %s' % jpgPath)

    # 4个tif ==============================================================================
    if satelliteName == 'TERRA':
        satelliteName1 = 'Terra'
    else:
        satelliteName1 = 'Aqua'
    tifNameDict = {'.l2.tif': 'TH_MODIS_%s_%s.tif' % (issue[0:8], issue[8:12]),
                   '.org.tif': 'TH_Break_%s_%s_%s.tif' % (satelliteName1, issue[0:8], issue[8:12]),
                   '.cloud.tif': 'TH_cloud_%s_%s_%s.tif' % (satelliteName1, issue[0:8], issue[8:12]),
                   '.tif': 'TH_shuihua_%s_%s_%s.tif' % (satelliteName1, issue[0:8], issue[8:12])}
    for key in tifNameDict.keys():
        tifPath = os.path.join(jsonDir, jsonBasename.replace('.json', key))
        tifCopyPath = os.path.join(copyDir, tifNameDict[key])
        if os.path.exists(tifPath):
            if os.path.exists(tifCopyPath):
                os.remove(tifCopyPath)
            shutil.copyfile(tifPath, tifCopyPath)
        else:
            print('Cannot Find %s' % tifPath)

    # 2个excel ==============================================================================
    xlsxNameDict = {'.xlsx': '%s_MODIS_%s_%s_%s_%s_%s_%s_BJ.MOD02QKM_TH_ext_algt_EXCEL_res.xlsx'
                             % (satelliteName, issue[0:4], issue[4:6], issue[6:8], issue[8:10], issue[10:12], '00'),
                    '_wx.xlsx': '%s_MODIS_%s_%s_%s_%s_%s_%s_BJ.MOD02QKM_TH_ext_algt_EXCEL_resWX.xlsx'
                             % (satelliteName, issue[0:4], issue[4:6], issue[6:8], issue[8:10], issue[10:12], '00')
                    }
    for key in xlsxNameDict.keys():
        xlsxPath = os.path.join(jsonDir, jsonBasename.replace('.json', key))
        xlsxCopyPath = os.path.join(copyDir, xlsxNameDict[key])
        if os.path.exists(xlsxPath):
            if os.path.exists(xlsxCopyPath):
                os.remove(xlsxCopyPath)
            shutil.copyfile(xlsxPath, xlsxCopyPath)
        else:
            print('Cannot Find %s' % xlsxPath)

    # 3个word ==============================================================================
    wordNameDict = {'.docx': '太湖蓝藻水华监测日报-%s%s.docx' % (issue[0:8], satelliteType),
                    '_jsem.docx': '%s年%s月%s日江苏省太湖蓝藻遥感监测日报.docx'
                                  % (int(issue[0:4]), int(issue[4:6]), int(issue[6:8])),
                    '_quick.docx': '未会商报告-%s%s.docx' % (issue[0:8], satelliteType)
                    }
    for key in wordNameDict.keys():
        docxPath = os.path.join(jsonDir, jsonBasename.replace('.json', key))
        docxCopyPath = os.path.join(copyDir, wordNameDict[key])
        if os.path.exists(docxPath):
            if os.path.exists(docxCopyPath):
                os.remove(docxCopyPath)
            shutil.copyfile(docxPath, docxCopyPath)
        else:
            print('Cannot Find %s' % docxPath)

    # 1个txt ==============================================================================
    txtNameDict = {'.txt': '太湖蓝藻水华监测日报-%s%s.txt' % (issue[0:8], satelliteType)}
    for key in txtNameDict.keys():
        txtPath = os.path.join(jsonDir, jsonBasename.replace('.json', key))
        txtCopyPath = os.path.join(copyDir, txtNameDict[key])
        if os.path.exists(txtPath):
            if os.path.exists(txtCopyPath):
                os.remove(txtCopyPath)
            shutil.copyfile(txtPath, txtCopyPath)
        else:
            print('Cannot Find %s' % txtPath)

    # 压缩
    zipRootDir = os.path.dirname(copyDir)
    zipFileName = os.path.basename(copyDir) + '.zip'
    zipFilePath = os.path.join(zipRootDir, zipFileName)
    if os.path.exists(zipFilePath):
        os.remove(zipFilePath)
    os.system('cd %s && zip -r %s %s' % (zipRootDir, zipFileName, os.path.basename(copyDir)))
    print('Zip Successful.')


if __name__ == '__main__':
    # jsonPath = r'C:\Users\Administrator\Desktop\model\output\6ce5de13-da13-11ea-871a-0242ac110003\20201112132011\TERRA_MODIS_L2_202006301032_250_00_00_taihu_algae_ndvi.json'

    jsonPath = sys.argv[1]
    main(jsonPath)
    print('Finish')