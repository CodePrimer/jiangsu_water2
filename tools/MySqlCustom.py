# -*- coding: utf-8 -*-
# @Author : wangbin
# @Time : 2020/8/22 17:57

import logging
import pymysql


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(filename)s[%(funcName)s line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# SQLFormula Example:
# SQL_1 = 'SELECT * FROM t_export_image WHERE acquire_time={acquire_time} AND is_deleted={is_deleted};'
# SQL_2 = 'DELETE FROM t_export_image_20201204 WHERE model_uuid={model_uuid};'
# SQL_3 = 'SELECT * FROM t_export_image_20201204 WHERE cloud IN {cloud};'
# SQL_4 = 'INSERT INTO t_admin (id,admin) VALUES {values};'


def SQLStringInterface(sqlFormula, sqlData):

    """
    对预存的MYSQL语句添加数据形成完整的SQL语句
    @param sqlFormula: str 预存MYSQL语句
    @param sqlData: dict 替换字典
    @return:
    """
    if not isinstance(sqlFormula, str):
        return
    if not isinstance(sqlData, dict):
        return

    if len(sqlData) == 0:
        sqlString = sqlFormula
    else:
        for each in sqlData:
            if each not in sqlFormula:
                continue
            if isinstance(sqlData[each], str):
                sqlFormula = sqlFormula.replace('{%s}' % each, '"%s"' % sqlData[each])
            else:
                sqlFormula = sqlFormula.replace('{%s}' % each, str(sqlData[each]))
        sqlString = sqlFormula
    return sqlString


def executeSql(loginInfo, sqlString):
    """
    执行一句SQL语句
    @param loginInfo: dict 登陆信息
    @param sqlString: str SQL语句
    @return:
    """
    # 登陆数据库
    try:
        datebase = loginInfo['dbname']
        username = loginInfo['user']
        password = loginInfo['pwd']
        host = loginInfo['host']
        port = loginInfo['port']
        if not isinstance(port, int):
            port = int(port)
        # 连接数据库
        conn = pymysql.connect(db=datebase, user=username, password=password, host=host, port=port)
    except Exception as e:
        logging.error('Login Failed!')
        logging.error(str(e))
        return
    logging.info('Login Success.')

    # 执行语句
    cursor = conn.cursor()
    try:
        cursor.execute(sqlString)
        sqlResult = cursor.fetchall()
        conn.commit()
    except Exception as e:
        logging.error('Execute SQL Failed!')
        logging.info(str(e))
        cursor.close()
        conn.close()
        return
    logging.info('Execute Success.')
    cursor.close()
    conn.close()
    return sqlResult


def executeSqlBatch(loginInfo, sqlStringList):

    # 登陆数据库
    try:
        datebase = loginInfo['dbname']
        username = loginInfo['user']
        password = loginInfo['pwd']
        host = loginInfo['host']
        port = loginInfo['port']
        if not isinstance(port, int):
            port = int(port)
        # 连接数据库
        conn = pymysql.connect(db=datebase, user=username, password=password, host=host, port=port)
    except Exception as e:
        logging.error('Login Failed!')
        logging.error(str(e))
        return
    logging.info('Login Success.')

    # 批量执行语句
    cursor = conn.cursor()
    index = 0
    totalIndex = len(sqlStringList)
    for sqlString in sqlStringList:
        try:
            cursor.execute(sqlString)
            sqlResult = cursor.fetchall()
            conn.commit()
            index += 1
        except Exception as e:
            logging.error('Execute SQL Failed!')
            logging.info(str(e))
            cursor.close()
            conn.close()
            return
        logging.info('Execute Success: %d/%d.' %(index, totalIndex))

    cursor.close()
    conn.close()


if __name__ == '__main__':

    # 登陆信息
    host = '10.16.56.6'
    dbname = 'jiangsu_water'
    user = 'root'
    pwd = '123456'
    port = 3306
    login = {'host': host, 'dbname': dbname, 'user': user, 'pwd': pwd, 'port': port}

    sql_form = 'SELECT * FROM t_export_image_20201204 WHERE cloud IN {cloud};'
    sql_data = {'cloud': (23, 99, 100)}
    sql_str = SQLStringInterface(sql_form, sql_data)

    executeSql(login, sql_str)
    # executeSqlBatch(login, [sql_str1, sql_str2])

    print('Finish')


