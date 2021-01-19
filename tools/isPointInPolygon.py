# -*- coding: utf-8 -*-


def isPointInPolygon(point, polygon):
    """
    :param point:
    :param polygon:     # [[0,0],[1,1],[0,1],[0,0]]
    :return:
    """
    # 判断是否在外包矩形内，如果不在，直接返回false
    lngList = []
    latList = []
    for i in range(len(polygon) - 1):
        lngList.append(polygon[i][0])
        latList.append(polygon[i][1])
    # print(lngList, latList)
    maxLng = max(lngList)
    minLng = min(lngList)
    maxLat = max(latList)
    minLat = min(latList)
    # print(maxLng, minLng, maxLat, minLat)
    if point[0] > maxLng or point[0] < minLng or point[1] > maxLat or point[1] < minLat:    # 在外包矩形之外的点
        return False
    count = 0
    point1 = polygon[0]
    for i in range(1, len(polygon)):
        point2 = polygon[i]
        # 点与多边形顶点重合
        if (point[0] == point1[0] and point[1] == point1[1]) or (point[0] == point2[0] and point[1] == point2[1]):
            # print("点在顶点上")
            return False
        # 判断线段两端点是否在射线两侧 不在肯定不相交 射线（-∞，lat）（lng,lat）
        if (point1[1] < point[1] <= point2[1]) or (point1[1] >= point[1] > point2[1]):
            # 求线段与射线交点 再和lat比较
            point12lng = point2[0] - (point2[1] - point[1]) * (point2[0] - point1[0]) / (point2[1] - point1[1])
            # print(point12lng)
            # 点在多边形边上
            if point12lng == point[0]:
                # print("点在多边形边上")
                return False
            if point12lng < point[0]:
                count += 1
        point1 = point2
    # print(count)
    if count % 2 == 0:
        return False
    else:
        return True


if __name__ == '__main__':
    flag = isPointInPolygon([0.8, 0.5], [[0, 0], [1, 1], [0, 1], [0, 0]])
    print(flag)