# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CityComputeDialog
                                 A QGIS plugin
 a plugin that compute cities' data
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-12-10
        git sha              : $Format:%H$
        copyright            : (C) 2024 by daishu
        email                : daishu10000@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import sys
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

from qgis.core import QgsRasterLayer, QgsVectorLayer,QgsVectorFileWriter,QgsProject, QgsField,QgsGeometry,QgsFeature,QgsFeedback
import processing
import glob
import rasterio
import numpy as np
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import csv
import pandas as pd

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'city_compute_dialog_base.ui'))


class CityComputeDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(CityComputeDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.pbRun.clicked.connect(self.onPbRunClicked)
        self.pbRun2.clicked.connect(self.onPbRun2Clicked)
        self.pb2Vector.clicked.connect(self.onPb2VectorClicked)
        self.pbPopulation.clicked.connect(self.onPbPopulationClicked)
        self.pbOutputCsv.clicked.connect(self.onPbOutputCsvClicked)
        self.pbCenter.clicked.connect(self.onPbCenterClicked)

    def onPbRunClicked(self):
        raster_layer=self.mlRaster.currentLayer()
        vector_layer=self.mlVector.currentLayer()

        # 检查图层是否有效
        if not raster_layer or not vector_layer:
            QtWidgets.QMessageBox.warning(self, "Error", "Please select both a raster and a vector layer.")
            return

        # 设置保存目录
        output_folder = r"D:\\socialComputeData"
        # 如果目录不存在，则创建目录
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"目录 {output_folder} 已创建。")

        raster_path = raster_layer.dataProvider().dataSourceUri()  # 获取光栅图层路径

        i=0
        # 遍历矢量图层的每个行政区
        for feature in vector_layer.getFeatures():
            i+=1

            admin_name = feature['市']  # 替换为行政区名称字段
            output_path = os.path.join(output_folder, f"{admin_name}_population.tif")

            # 获取每个feature的几何形状
            geometry = feature.geometry()

            # 如果几何形状为空，跳过该特征
            if geometry.isEmpty():
                continue

            # 创建临时掩膜图层（基于特征的几何形状）
            mask_layer = QgsVectorLayer('Polygon?crs=' + vector_layer.crs().authid(), 'Mask', 'memory')
            mask_provider = mask_layer.dataProvider()

            # 将当前feature的几何形状添加到掩膜图层
            mask_provider.addFeatures([feature])

            # 临时保存掩膜图层为内存图层的路径
            mask_path = os.path.join(output_folder, f"mask_{admin_name}.shp")
            mask_layer.dataProvider().createSpatialIndex()  # 创建空间索引

            # 保存掩膜图层为Shapefile
            mask_layer.commitChanges()
            QgsVectorFileWriter.writeAsVectorFormat(mask_layer, mask_path, 'utf-8', mask_layer.crs(), 'ESRI Shapefile')

            print(raster_path)
            print(mask_path)

            # 构建裁剪处理参数
            params = {
                'INPUT': raster_path,
                'MASK': mask_path,
                'OUTPUT': output_path
            }

            # 执行裁剪操作
            processing_result = processing.run('gdal:cliprasterbymasklayer', params)

            if processing_result['OUTPUT']:
                print(f"完成裁剪: {admin_name} -> {output_path}")
            else:
                print(f"裁剪失败: {admin_name}")
        print("所有数据裁剪完成!")
    def onPbRun2Clicked(self):
        # 调用函数，传入文件夹路径
        folder_path = r"D:\socialComputeData"  # 请替换为你的文件夹路径
        self.process_tif_files(folder_path)

    def onPb2VectorClicked(self):
        self.load_tif_files()
    def onPbPopulationClicked(self):
        # 文件夹路径
        vector_folder = r'D:\socialComputeData\vector2'
        output_folder = r'D:\socialComputeData\vector3'

        raster_layer=self.mlRaster.currentLayer()

        # 获取所有 .shp 文件
        shp_files = [f for f in os.listdir(vector_folder) if f.endswith('.shp')]

        i=0
        # 处理每个shp文件
        for shp_file in shp_files:
            i+=1
            # 构建shp文件路径
            shp_path = os.path.join(vector_folder, shp_file)

            # 加载Shapefile图层
            vector_layer = QgsVectorLayer(shp_path, shp_file, 'ogr')

            if not vector_layer.isValid():
                print(f"无法加载图层: {shp_file}")
                continue

            # 克隆数据提供器，不修改原始图层
            provider = vector_layer.dataProvider()
            fields = provider.fields()  # 获取字段定义
            features = list(provider.getFeatures())  # 获取所有要素

            # 创建新的副本图层
            vector_layer_copy = QgsVectorLayer("Polygon?crs="+vector_layer.crs().authid(), "copy_layer", "memory")
            new_provider = vector_layer_copy.dataProvider()
            new_provider.addAttributes(fields)  # 添加字段
            vector_layer_copy.updateFields()  # 更新图层

            # 插入要素到副本图层
            new_provider.addFeatures(features)

            # 设置分区统计参数
            params = {
                'INPUT_VECTOR': vector_layer_copy,
                'INPUT_RASTER': raster_layer,
                'STATISTICS': 1,
            }

            # 使用分区统计工具进行栅格统计
            processing.run("qgis:zonalstatistics", params)

            features = list(new_provider.getFeatures())  # 获取所有要素

            # 创建一个新的列表存储过滤后的要素
            filtered_features = []
            for feature in features:
                raster_sum = feature['_sum']
                if raster_sum >= 100000:
                    filtered_features.append(feature)

            # 清除现有要素，添加过滤后的要素
            new_provider.deleteFeatures([f.id() for f in vector_layer_copy.getFeatures()])
            new_provider.addFeatures(filtered_features)

            # 构建输出 Shapefile 文件路径
            output_shp_path = os.path.join(output_folder, f'processed_{shp_file}')

            # 保存新的Shapefile文件
            QgsVectorFileWriter.writeAsVectorFormat(vector_layer_copy, output_shp_path, "utf-8", vector_layer_copy.crs(),
                                                    "ESRI Shapefile")

            print(f"已处理并保存: {output_shp_path}")

        print("所有文件处理完成！")

    def onPbOutputCsvClicked(self):
        folder_path = r"D:\socialComputeData\vector3"  # 替换为实际的文件夹路径
        output_csv_path = r"D:\socialComputeData\csv\data.csv"  # 替换为输出文件路径

        self.read_sum_attributes_from_shp(folder_path, output_csv_path)

    def onPbCenterClicked(self):
        csvPath=r"D:\socialComputeData\csv\data.csv"
        outPath=r"D:\socialComputeData\csv\data2.csv"
        # 读取CSV文件
        df = pd.read_csv(csvPath)

        # 拷贝原数据
        df_copy = df.copy()

        # 检查'_sum_2'列是否有数据
        if df_copy['_sum_2'].isna().all():  # 如果'_sum_2'列全部缺失
            # 设置center, max, sd列为0
            df_copy['center'] = 0
            df_copy['max'] = 0
            df_copy['sd'] = 0
        else:
            # 获取'_sum_1'到'_sum_15'的列
            sum_columns = [f'_sum_{i}' for i in range(1, 16)]

            # 计算max列：取'_sum_1'到'_sum_15'中有效值的最大值
            df_copy['max'] = df_copy[sum_columns].max(axis=1, skipna=True)

            # 计算sd列：取'_sum_1'到'_sum_15'中有效值的标准差
            df_copy['sd'] = df_copy[sum_columns].std(axis=1, skipna=True)

            # 计算center列：1 - 2 * sd / max
            df_copy['center'] = 1 - 2 * df_copy['sd'] / df_copy['max']

            # 如果sd为NaN（可能是因为max是0），将center列设置为0
            df_copy['center'] = df_copy['center'].fillna(0)

        # 保存处理后的数据到新文件
        df_copy.to_csv(outPath, index=False)

        print("文件处理完成，保存为"+outPath)

    def process_tif_files(self,folder_path):
        # 使用 glob 查找所有 .tif 文件
        tif_files = glob.glob(os.path.join(folder_path, "*.tif"))

        i=0
        for tif_file in tif_files:
            i+=1

            cityName=os.path.basename(tif_file).split("_")[0]
            print(cityName)
            splitNum=90
            if cityName in ["北京市","上海市","广州市","深圳市","天津市"]:
                splitNum = 95
            percentiles = self.get_band_1_percentiles(tif_file,[splitNum])

            print(
                f"{cityName} 的分位数 {percentiles[0]}")

            # 计算大于分位数的区域并保存新栅格图层
            self.create_threshold_raster(tif_file, percentiles[0])


    def get_band_1_percentiles(self,tif_file, percentiles=[90,95]):

        with rasterio.open(tif_file) as src:
            # 获取波段1的数据
            band1 = src.read(1)  # 波段1通常是索引0

            # 移除无效值（通常是NaN或特定的无效值，按需要调整）
            band1 = band1[band1 != src.nodata]  # 去除无效值

            # 计算指定的分位数
            band1_percentiles = np.percentile(band1, percentiles)
            return band1_percentiles

    def create_threshold_raster(self, tif_file, threshold):
        with rasterio.open(tif_file) as src:
            # 读取波段1数据
            band1 = src.read(1)

            # 计算大于分位数的区域
            thresholded_band = band1 > threshold

            # 获取元数据，用于新文件
            meta = src.meta

            # 更新数据类型
            meta.update(dtype=rasterio.uint8, count=1, nodata=0)

            # 获取输入文件名（不带扩展名）
            input_filename = os.path.splitext(os.path.basename(tif_file))[0]

            folder_path = r"D:\socialComputeData\split"  # 请替换为你的文件夹路径

            # 构造输出文件路径
            output_file = os.path.join(folder_path, f"{input_filename}_threshold.tif")

            print(output_file)
            # 写入新的栅格图层
            with rasterio.open(output_file, 'w', **meta) as dest:
                dest.write(thresholded_band.astype(rasterio.uint8), 1)
            print(f"生成的新栅格图层保存为: {output_file}")

    def load_tif_files(self):
        # 指定文件夹路径
        folder = r"D:\socialComputeData\split"
        output_folder = r"D:\socialComputeData\vector2"

        raster_layer = self.mlRaster.currentLayer()  # 获取当前的栅格图层
        raster_path = raster_layer.dataProvider().dataSourceUri()  # 获取光栅图层路径
        print(raster_path)

        if not os.path.exists(folder):
            print( "文件夹不存在", f"指定的文件夹路径 {folder} 不存在。")
            return

        # 获取文件夹中所有.tif文件
        tif_files = [f for f in os.listdir(folder) if f.endswith('.tif')]

        if not tif_files:
            print( "没有找到TIF文件", f"文件夹 {folder} 中没有找到任何 .tif 文件。")
            return

        i=0
        for tif_file in tif_files:
            i+=1
            file_path = os.path.join(folder, tif_file)
            print(f"正在处理文件: {file_path}")

            # 读取栅格文件
            with rasterio.open(file_path) as src:
                image = src.read(1)  # 读取第一波段数据
                transform = src.transform
                # 获取栅格数据的形状
                mask = image != src.nodata

                # 提取栅格数据中的形状
                results = shapes(image, mask=mask, transform=transform)

                # 将提取的形状转换为GeoDataFrame
                polygons = []
                for result in results:
                    geom, value = result
                    polygons.append(shape(geom))

                # 创建GeoDataFrame
                gdf = gpd.GeoDataFrame({'geometry': polygons})

                # 为GeoDataFrame设置CRS为栅格的原始坐标系
                gdf.set_crs(src.crs, allow_override=True, inplace=True)

                # 坐标系转换为 EPSG:3857
                gdf = gdf.to_crs(epsg=3857)

                # 计算每个多边形的面积（单位是平方米）
                gdf['area'] = gdf.geometry.area

                # 删除面积小于3平方千米的多边形（3平方千米 = 3 * 10^6 平方米）
                gdf = gdf[gdf['area'] >= 3 * 10**6]

                # 保存为Shapefile
                output_file = os.path.join(output_folder, f"{os.path.splitext(tif_file)[0]}.shp")
                gdf.to_file(output_file)
                print(f"保存为矢量文件: {output_file}")

    def read_sum_attributes_from_shp(self,folder_path, output_csv_path):
        """
        遍历指定文件夹中的所有.shp文件，提取每个文件的_sum属性值，输出到表格中。

        :param folder_path: 包含.shp文件的文件夹路径
        :param output_csv_path: 输出的CSV文件路径
        """
        # 初始化存储结果的列表
        result_data = []

        # 遍历文件夹中的所有.shp文件
        for file_name in os.listdir(folder_path):
            if file_name.endswith(".shp"):
                file_path = os.path.join(folder_path, file_name)

                # 加载Shapefile文件
                layer = QgsVectorLayer(file_path, file_name, "ogr")
                if not layer.isValid():
                    print(f"无法加载文件: {file_name}")
                    continue

                # 提取_sum属性
                sum_values = []
                for feature in layer.getFeatures():
                    if "_sum" in feature.fields().names():
                        sum_values.append(feature["_sum"])
                    else:
                        sum_values.append("N/A")  # 如果没有_sum属性，填充N/A

                # 生成当前文件的行数据
                row_data = [file_name] + sum_values
                result_data.append(row_data)

        # 获取最大列数，确保表格对齐
        max_columns = max(len(row) for row in result_data)

        # 输出结果到CSV文件
        with open(output_csv_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            # 写入表头
            header = ["FileName"] + [f"_sum_{i + 1}" for i in range(max_columns - 1)]
            writer.writerow(header)

            # 写入数据
            for row in result_data:
                # 填充缺失的列
                row += [""] * (max_columns - len(row))
                writer.writerow(row)

        print(f"数据已成功写入: {output_csv_path}")