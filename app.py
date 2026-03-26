# -*- coding: utf-8 -*-
"""
阶段 4：可视化图表与 AI 算法植入 (Data Visualization & AI Engine)
纯净读取版 - 静默读取后台数据文件，无需前端上传
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import re
from datetime import datetime, timedelta
import os

# ============================================================
# 数据文件路径配置（管理员可修改此处）
# ============================================================
# 数据文件名称 - 放在 app.py 同级目录下
SALES_FILE = "销量统计.xlsx"
FORECAST_FILE = "销量预测.xlsx"
PRODUCT_FILE = "产品运营信息表.xlsx"
MARKET_FILE = "大盘趋势表.xlsx"

# 支持的文件扩展名（优先级从高到低）
SUPPORTED_EXTENSIONS = ['.xlsx', '.xls', '.csv']

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="实际销量与预测趋势对比分析及智能备货看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 自定义 CSS (清爽白色主题)
# ============================================================
st.markdown("""
<style>
    /* 主容器背景 - 白色渐变 */
    .stApp {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 50%, #f0f2f5 100%);
    }

    /* 侧边栏背景 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
        border-right: 2px solid #e1e4e8;
    }

    /* 主标题样式 */
    h1 {
        color: #0366d6 !important;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 600;
    }

    /* 副标题样式 */
    h2, h3 {
        color: #24292e !important;
        font-family: 'Segoe UI', sans-serif;
    }

    /* 数据表格样式 */
    .dataframe {
        background-color: #ffffff !important;
        color: #24292e !important;
        border: 1px solid #e1e4e8 !important;
        border-radius: 8px !important;
    }

    .dataframe th {
        background-color: #f6f8fa !important;
        color: #0366d6 !important;
        font-weight: 600;
    }

    /* 筛选器标签样式 */
    label[data-testid="stWidgetLabel"] {
        color: #24292e !important;
        font-weight: 600;
    }

    /* 按钮样式 */
    .stButton>button {
        background: linear-gradient(90deg, #0366d6 0%, #0056b3 100%);
        color: white;
        border: none;
        border-radius: 6px;
    }

    /* AI 诊断卡片样式 */
    .ai-card {
        background: linear-gradient(135deg, #e8f4ff 0%, #ffffff 100%);
        border: 2px solid #b3d7ff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(3, 102, 214, 0.15);
    }

    .ai-alert-danger {
        background: linear-gradient(135deg, #ffe8e8 0%, #fff5f5 100%);
        border-left: 4px solid #dc3545;
    }

    .ai-alert-warning {
        background: linear-gradient(135deg, #fff3cd 0%, #fffbf0 100%);
        border-left: 4px solid #ffc107;
    }

    .ai-alert-success {
        background: linear-gradient(135deg, #d4edda 0%, #f0fff4 100%);
        border-left: 4px solid #28a745;
    }

    .ai-header {
        color: #0366d6;
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 12px;
        border-bottom: 2px solid #0366d6;
        padding-bottom: 8px;
    }

    .ai-section {
        margin: 12px 0;
        padding: 12px;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.7);
    }

    .ai-label {
        color: #586069;
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 4px;
    }

    .ai-value {
        color: #24292e;
        font-size: 16px;
        font-weight: 600;
    }

    .ai-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin: 4px;
    }

    .badge-peak {
        background: #d4edda;
        color: #155724;
    }

    .badge-low {
        background: #f8d7da;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 业务规则字典：数据清洗与匹配
# ============================================================

# 国家编码映射
COUNTRY_MAPPING = {
    '日本': 'JP',
    '加拿大': 'CA',
    '美国': 'US',
    '墨西哥': 'MX',
    '澳洲': 'AU',
    '德国': 'DE',
    '英国': 'UK'
}

def map_country_code(country_name):
    """国家编码映射与兜底规则"""
    if pd.isna(country_name):
        return 'DE'
    for cn_name, code in COUNTRY_MAPPING.items():
        if cn_name in str(country_name):
            return code
    return 'DE'  # 兜底规则

def clean_category_name(category_name):
    """去除类目名称末尾的无意义后缀"""
    if pd.isna(category_name):
        return category_name
    suffixes = ['收纳', '品线', '系列']
    cleaned = str(category_name)
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            break
    return cleaned.strip()

def find_data_file(base_filename):
    """
    查找数据文件（支持多种格式）
    按优先级查找：.xlsx > .xls > .csv
    """
    for ext in SUPPORTED_EXTENSIONS:
        filepath = base_filename.replace('.xlsx', '').replace('.xls', '') + ext
        if os.path.exists(filepath):
            return filepath
    return None

def parse_forecast_dates(df_forecast):
    """
    将预测表的列按月归集（支持"3月16日"、"6月PD"等多种格式）
    返回: 按FNSKU分组的月度预测DataFrame（不包含站点，支持1-12月）
    """
    monthly_data = []

    for idx, row in df_forecast.iterrows():
        fnsku = row['FNSKU']

        # 初始化1-12月的月度合计
        monthly_totals = {f'2026-{m:02d}': 0 for m in range(1, 13)}

        for col in df_forecast.columns:
            if col in ['站点FNSKU', 'FNSKU', '站点', '控销/断货标签', '备注']:
                continue

            value = row[col]
            if pd.isna(value) or value == 0:
                continue

            # 优先处理"X月Y日"格式（如"3月16日"、"3月23日"）
            date_match = re.search(r'(\d+)月\d+日', str(col))
            if date_match:
                month = int(date_match.group(1))
                month_key = f'2026-{month:02d}'
                if 1 <= month <= 12 and month_key in monthly_totals:
                    monthly_totals[month_key] += value
                continue

            # 处理"X月PD"格式（如"6月PD"）
            pd_month_match = re.search(r'(\d+)月PD', str(col), re.IGNORECASE)
            if pd_month_match:
                month = int(pd_month_match.group(1))
                month_key = f'2026-{month:02d}'
                if 1 <= month <= 12 and month_key in monthly_totals:
                    monthly_totals[month_key] += value
                continue

            # 处理纯PD列
            if str(col).strip().upper() == 'PD':
                # PD默认为6月（Prime Day）
                month_key = '2026-06'
                if month_key in monthly_totals:
                    monthly_totals[month_key] += value
                continue

            # 处理日期编号列（Excel日期数字）
            try:
                excel_date_num = int(col)
                forecast_date = datetime(1899, 12, 30) + timedelta(days=excel_date_num)

                if forecast_date.year == 2026:
                    month_key = forecast_date.strftime('%Y-%m')
                    if month_key in monthly_totals:
                        monthly_totals[month_key] += value
            except (ValueError, TypeError):
                continue

        # 添加所有1-12月的数据（不仅限于3-7月）
        for month_key, total in monthly_totals.items():
            if total > 0:  # 仅添加有数据的月份
                monthly_data.append({
                    'FNSKU': fnsku,
                    '预测月份': month_key,
                    '预测销量': total
                })

    df_monthly_forecast = pd.DataFrame(monthly_data)

    # 按FNSKU聚合（同一FNSKU的同一月份可能有多个站点数据，需要聚合）
    df_monthly_forecast = df_monthly_forecast.groupby(['FNSKU', '预测月份'])['预测销量'].sum().reset_index()

    return df_monthly_forecast

# ============================================================
# 数据处理管道（完整版）
# ============================================================

@st.cache_data
def load_and_process_data():
    """
    静默读取4个数据文件并处理
    返回: (df_final, df_market, df_forecast_monthly, df_forecast_pivot, status_msg)
    """
    try:
        # 查找数据文件
        sales_path = find_data_file(SALES_FILE)
        product_path = find_data_file(PRODUCT_FILE)
        forecast_path = find_data_file(FORECAST_FILE)
        market_path = find_data_file(MARKET_FILE)

        # 检查文件是否存在
        missing_files = []
        if sales_path is None:
            missing_files.append(SALES_FILE)
        if product_path is None:
            missing_files.append(PRODUCT_FILE)
        if forecast_path is None:
            missing_files.append(FORECAST_FILE)
        if market_path is None:
            missing_files.append(MARKET_FILE)

        if missing_files:
            return None, None, None, None, f"⚠️ 未检测到以下数据文件：<br>{'<br>'.join(missing_files)}<br><br>请管理员上传最新的源数据表到项目目录。"

        # 读取原始文件（根据扩展名选择读取方式）
        if sales_path.endswith('.csv'):
            df_sales = pd.read_csv(sales_path, encoding='utf-8-sig')
        else:
            df_sales = pd.read_excel(sales_path)

        if product_path.endswith('.csv'):
            df_product = pd.read_csv(product_path, encoding='utf-8-sig')
        else:
            df_product = pd.read_excel(product_path)

        if forecast_path.endswith('.csv'):
            df_forecast = pd.read_csv(forecast_path, encoding='utf-8-sig')
        else:
            df_forecast = pd.read_excel(forecast_path)

        if market_path.endswith('.csv'):
            df_market = pd.read_csv(market_path, encoding='utf-8-sig')
        else:
            df_market = pd.read_excel(market_path)

        # 增强列名鲁棒性 - 防止日期被识别为 Timestamp
        df_sales.columns = [str(c) for c in df_sales.columns]
        df_product.columns = [str(c) for c in df_product.columns]
        df_forecast.columns = [str(c) for c in df_forecast.columns]
        df_market.columns = [str(c) for c in df_market.columns]

        # 处理销量统计表
        sales_cols = ['FNSKU', 'SKU', '国家', '一级分类', '二级分类', '品牌', '主推标签', '利润标签', 'Listing定位']
        sales_cols += [col for col in df_sales.columns if re.match(r'\d{4}-\d{2}', col)]
        df_sales_clean = df_sales[[col for col in sales_cols if col in df_sales.columns]].copy()
        df_sales_clean['国家代码'] = df_sales_clean['国家'].apply(map_country_code)

        # 处理产品运营信息表
        product_cols = ['FNSKU', 'SKU', 'SKU名称', '类目', '品牌', '是否自研', '主推标签', '利润标签', 'Listing定位', 'Listing状态']
        df_product_clean = df_product[[col for col in product_cols if col in df_product.columns]].copy()
        df_product_clean = df_product_clean.drop_duplicates(subset=['FNSKU'], keep='last')

        # 处理销量预测表
        df_forecast_monthly = parse_forecast_dates(df_forecast)

        # 按类目聚合预测数据
        df_forecast_with_category = pd.merge(
            df_forecast_monthly,
            df_product_clean[['FNSKU', '类目']],
            on='FNSKU',
            how='left'
        )

        # 按类目聚合月度预测数据
        df_forecast_by_category = df_forecast_with_category.groupby(['类目', '预测月份'])['预测销量'].sum().reset_index()

        # 转换为类目-月份透视表格式
        df_forecast_pivot = df_forecast_by_category.pivot(
            index='类目',
            columns='预测月份',
            values='预测销量'
        ).reset_index()

        # 重命名列
        df_forecast_pivot.columns.name = None

        # 确保所有1-12月都存在（如果缺失则添加并填充为0）
        all_months = [f'2026-{m:02d}' for m in range(1, 13)]
        for month in all_months:
            if month not in df_forecast_pivot.columns:
                df_forecast_pivot[month] = 0

        # 重命名月份列为预测_格式
        month_rename_map = {}
        for col in df_forecast_pivot.columns:
            if col != '类目':
                if col.startswith('2026-'):
                    month_rename_map[col] = f'预测_{col}'

        df_forecast_pivot = df_forecast_pivot.rename(columns=month_rename_map)

        # 处理大盘走势表
        df_market['类目_清洗'] = df_market['类目'].apply(clean_category_name)
        df_market['年月_标准'] = df_market['年月'].apply(lambda x: x if re.match(r'\d{4}-\d{2}', str(x)) else str(x))
        df_market['年份'] = df_market['年月_标准'].apply(lambda x: int(x.split('-')[0]) if '-' in str(x) else None)
        df_market['月份'] = df_market['年月_标准'].apply(lambda x: int(x.split('-')[1]) if '-' in str(x) else None)

        # 合并数据
        df_merged = pd.merge(df_sales_clean, df_product_clean, on='FNSKU', how='left', suffixes=('_销量', '_产品'))
        df_merged = df_merged.rename(columns={'国家代码': '站点'})

        # 合并类目级预测数据（使用'类目'作为merge key）
        df_merged = pd.merge(df_merged, df_forecast_pivot, on='类目', how='left')

        # 整理最终列
        final_cols = [
            'FNSKU', 'SKU名称', '站点', '国家',
            '一级分类', '二级分类', '类目', '品牌', '是否自研',
            '主推标签', '利润标签', 'Listing定位', 'Listing状态'
        ]
        history_cols = [col for col in df_merged.columns if re.match(r'\d{4}-\d{2}', col) and '预测' not in col]
        final_cols.extend(history_cols)
        forecast_cols = [col for col in df_merged.columns if '预测' in col]
        final_cols.extend(forecast_cols)

        final_cols = [col for col in final_cols if col in df_merged.columns]
        df_final = df_merged[final_cols].copy()

        # 返回：销量数据、市场数据、FNSKU级预测数据、类目级预测数据
        return df_final, df_market, df_forecast_monthly, df_forecast_pivot, "✅ 数据加载成功"

    except FileNotFoundError as e:
        return None, None, None, None, f"⚠️ 未检测到后台数据文件，请管理员上传最新的源数据表。<br><br>错误详情：{str(e)}"
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return None, None, None, None, f"❌ 数据处理失败：{str(e)}<br><br>错误详情：{error_detail}"

# ============================================================
# 市场数据处理辅助函数
# ============================================================

def get_market_data_for_selection(df_market, country, category):
    """根据筛选条件获取市场数据"""
    if df_market is None or len(df_market) == 0:
        return None

    # 国家筛选
    if country != '全部':
        if country in COUNTRY_MAPPING.values():
            df_filtered = df_market[df_market['国家'] == country].copy()
        else:
            df_filtered = None
            for cn_name, code in COUNTRY_MAPPING.items():
                if cn_name in country:
                    df_filtered = df_market[df_market['国家'] == code].copy()
                    break
            if df_filtered is None:
                df_filtered = df_market.copy()
    else:
        df_filtered = df_market.copy()

    # 类目筛选（使用清洗后的类目）
    if category != '全部' and '类目_清洗' in df_filtered.columns:
        cleaned_category = clean_category_name(category)
        df_filtered = df_filtered[df_filtered['类目_清洗'] == cleaned_category].copy()

    return df_filtered


def transform_market_data_for_chart(df_market_filtered):
    """将市场数据转换为适合绘图的格式"""
    if df_market_filtered is None or len(df_market_filtered) == 0:
        return {}

    result = {}

    # 按年份分组
    for year in sorted(df_market_filtered['年份'].unique()):
        if pd.isna(year):
            continue

        year_data = df_market_filtered[df_market_filtered['年份'] == year]

        # 按月份聚合
        monthly_totals = [0] * 12
        for _, row in year_data.iterrows():
            month = int(row['月份'])
            if 1 <= month <= 12:
                monthly_totals[month - 1] += row['销量']

        result[year] = monthly_totals

    return result

# ============================================================
# AI 算法实现
# ============================================================

# 算法 A：3个月滑动平均找淡旺季
def algorithm_a_seasonal_analysis(row):
    """
    算法 A：3个月滑动平均找淡旺季
    """
    monthly_avg = {}
    for month in range(1, 13):
        month_2024 = f'2024-{month:02d}'
        month_2025 = f'2025-{month:02d}'
        val_2024 = row.get(month_2024, 0) if not pd.isna(row.get(month_2024, 0)) else 0
        val_2025 = row.get(month_2025, 0) if not pd.isna(row.get(month_2025, 0)) else 0
        monthly_avg[month] = (val_2024 + val_2025) / 2

    moving_avg = {}
    for month in range(1, 13):
        prev_month = month - 1 if month > 1 else 12
        next_month = month + 1 if month < 12 else 1
        moving_avg[month] = (monthly_avg[prev_month] + monthly_avg[month] + monthly_avg[next_month]) / 3

    peak_sum_max = -1
    peak_months = []
    for start in range(12):
        three_months = [(start + i) % 12 + 1 for i in range(3)]
        three_sum = sum(moving_avg[m] for m in three_months)
        if three_sum > peak_sum_max:
            peak_sum_max = three_sum
            peak_months = sorted(three_months)

    low_sum_min = float('inf')
    low_months = []
    for start in range(12):
        three_months = [(start + i) % 12 + 1 for i in range(3)]
        three_sum = sum(moving_avg[m] for m in three_months)
        if three_sum < low_sum_min:
            low_sum_min = three_sum
            low_months = sorted(three_months)

    return {
        'monthly_avg': monthly_avg,
        'moving_avg': moving_avg,
        'peak_months': peak_months,
        'low_months': low_months,
        'avg_total': sum(monthly_avg.values()) / 12
    }

# 算法 B：3:7 加权基准线排雷
def algorithm_b_risk_assessment(row, forecast_start='2026-03', forecast_end='2026-07'):
    """
    算法 B：3:7 加权基准线排雷
    """
    forecast_months = []
    current_year = int(forecast_start[:4])
    current_month = int(forecast_start[5:7])
    end_month = int(forecast_end[5:7])

    for m in range(current_month, end_month + 1):
        forecast_months.append(f'{current_year}-{m:02d}')

    weighted_baseline = 0
    for month in forecast_months:
        month_num = int(month[5:7])
        val_2025 = row.get(f'2025-{month_num:02d}', 0)
        if pd.isna(val_2025): val_2025 = 0
        weighted_baseline += val_2025 * 0.7
        val_2024 = row.get(f'2024-{month_num:02d}', 0)
        if pd.isna(val_2024): val_2024 = 0
        weighted_baseline += val_2024 * 0.3

    forecast_total = 0
    for month in forecast_months:
        val = row.get(f'预测_{month}', 0)
        if pd.isna(val): val = 0
        forecast_total += val

    deviation_rate = 0
    if weighted_baseline > 0:
        deviation_rate = (forecast_total - weighted_baseline) / weighted_baseline * 100

    diagnosis = ""
    diagnosis_type = ""
    if deviation_rate > 20:
        diagnosis = f"⚠️ 滞销/超备风险：当前预测过高，偏离加权同期基准 +{deviation_rate:.1f}%。请结合产品定位确认，若非爆发期新品，请防范库存积压。"
        diagnosis_type = "danger"
    elif deviation_rate < -20:
        diagnosis = f"🚨 断货风险：当前预测过于保守，偏离加权同期基准 {deviation_rate:.1f}%。请核实是否受限于供应链缺货或竞品打压，防范断货流失坑位。"
        diagnosis_type = "warning"
    else:
        diagnosis = "✅ 备货健康：预测贴合历史加权大盘走势。"
        diagnosis_type = "success"

    return {
        'forecast_months': forecast_months,
        'weighted_baseline': weighted_baseline,
        'forecast_total': forecast_total,
        'deviation_rate': deviation_rate,
        'diagnosis': diagnosis,
        'diagnosis_type': diagnosis_type
    }

# 创建双 Y 轴趋势图
def create_dual_axis_trend_chart(store_row, market_data, seasonal_result, selected_category, selected_years=None, selected_months=None):
    """
    创建双 Y 轴趋势图
    左 Y 轴：市场大盘趋势（大量级，面积图）
    右 Y 轴：店铺实际销量 + 预测（小量级）

    Args:
        store_row: 店铺数据（类目聚合后的Series或DataFrame）
        market_data: 市场数据字典 {year: [monthly_values]}
        seasonal_result: 季节性分析结果
        selected_category: 选中的类目名称
        selected_years: 选中的年份列表
        selected_months: 选中的月份列表
    """
    if selected_years is None:
        selected_years = [2025, 2026]
    if selected_months is None:
        selected_months = list(range(3, 8))  # 3-7月

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    months = list(range(1, 13))

    # 左 Y 轴：市场趋势数据（改为面积图，浅色半透明，高对比度配色）
    if market_data:
        # 高对比度配色：2024年用冷灰色，2025年用浅紫色，2026年用淡蓝色
        year_colors = {
            2024: '#78909C',  # 冷灰色 - 2024
            2025: '#A78BFA',  # 浅紫色 - 2025
            2026: '#60A5FA'   # 淡蓝色 - 2026
        }

        for year in sorted(market_data.keys()):
            if year not in selected_years:
                continue

            y_market = market_data[year]
            color = year_colors.get(year, '#95a5a6')

            # 转换为RGBA并设置透明度（0.25-0.3之间）
            if color.startswith('#'):
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                # 使用0.28透明度，让重叠部分能透出底色
                fill_color = f'rgba({r}, {g}, {b}, 0.28)'

            fig.add_trace(
                go.Scatter(
                    x=months, y=y_market, mode='lines',
                    name=f'市场 {year}',
                    line=dict(color=color, width=1.5),  # 保留细轮廓线
                    fill='tozeroy',  # 面积图
                    fillcolor=fill_color,  # 半透明填充色
                    legendgroup='market',
                    showlegend=True
                ),
                secondary_y=False
            )

    # 右 Y 轴：店铺实际销量（根据年份筛选显示）
    if 2024 in selected_years:
        y_2024 = [store_row.get(f'2024-{m:02d}', 0) for m in months]
        y_2024 = [0 if pd.isna(v) else v for v in y_2024]
        # 根据月份筛选设置显示值
        y_2024_filtered = [v if m in selected_months else None for m, v in zip(months, y_2024)]
        fig.add_trace(go.Scatter(
            x=months, y=y_2024_filtered, mode='lines+markers',
            name='店铺 2024实际', line=dict(color='#2ecc71', width=2),
            marker=dict(size=4), legendgroup='store', connectgaps=True
        ), secondary_y=True)

    if 2025 in selected_years:
        y_2025 = [store_row.get(f'2025-{m:02d}', 0) for m in months]
        y_2025 = [0 if pd.isna(v) else v for v in y_2025]
        # 根据月份筛选设置显示值
        y_2025_filtered = [v if m in selected_months else None for m, v in zip(months, y_2025)]
        fig.add_trace(go.Scatter(
            x=months, y=y_2025_filtered, mode='lines+markers',
            name='店铺 2025实际', line=dict(color='#3498db', width=3),
            marker=dict(size=4), legendgroup='store', connectgaps=True
        ), secondary_y=True)

    # 2026年数据（如果选中2026年）
    if 2026 in selected_years:
        # 2026年1-2月实际
        y_2026_actual = [store_row.get(f'2026-{m:02d}', 0) for m in [1, 2]]
        y_2026_actual = [0 if pd.isna(v) else v for v in y_2026_actual]
        fig.add_trace(go.Scatter(
            x=[1, 2], y=y_2026_actual, mode='lines+markers',
            name='店铺 2026实际', line=dict(color='#e74c3c', width=3),
            marker=dict(size=4), legendgroup='store'
        ), secondary_y=True)

        # 2026年3-7月预测（虚线，根据月份筛选）
        forecast_months_available = list(range(3, 8))
        forecast_data = []
        forecast_x = []
        for m in forecast_months_available:
            if m in selected_months:
                val = store_row.get(f'预测_2026-{m:02d}', 0)
                forecast_data.append(0 if pd.isna(val) else val)
                forecast_x.append(m)

        if forecast_data:
            fig.add_trace(go.Scatter(
                x=forecast_x, y=forecast_data, mode='lines+markers',
                name='店铺 2026预测', line=dict(color='#e74c3c', width=3, dash='dash'),
                marker=dict(size=4), legendgroup='store', connectgaps=True
            ), secondary_y=True)

    # 布局设置
    fig.update_xaxes(
        title_text="月份",
        tickmode='array',
        tickvals=list(range(1, 13)),
        ticktext=[f'{m}月' for m in range(1, 13)]
    )
    fig.update_yaxes(
        title_text="<b>市场销量</b>",
        title_font=dict(color="#95a5a6"),
        tickfont=dict(color="#95a5a6"),
        secondary_y=False
    )
    fig.update_yaxes(
        title_text="<b>店铺销量</b>",
        title_font=dict(color="#3498db"),
        tickfont=dict(color="#3498db"),
        secondary_y=True
    )
    fig.update_layout(
        title="销量趋势对比分析（市场 vs 店铺）",
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template='plotly_white',
        height=500
    )

    return fig

# ============================================================
# 侧边栏：筛选器
# ============================================================
with st.sidebar:
    st.markdown("# 📊 备货看板")
    st.markdown("---")

    # ============================================================
    # 数据加载状态显示
    # ============================================================
    st.markdown("### 📡 数据状态")

    # 首次加载时自动读取数据
    if 'df_processed' not in st.session_state:
        with st.spinner("正在加载数据..."):
            df, df_market, df_forecast_monthly, df_forecast_pivot, msg = load_and_process_data()
            if df is None or df_market is None:
                st.error(msg, icon="⚠️")
                st.stop()
            else:
                st.success(msg, icon="✅")
                st.session_state['df_processed'] = df
                st.session_state['df_market'] = df_market
                st.session_state['df_forecast_monthly'] = df_forecast_monthly
                st.session_state['df_forecast_pivot'] = df_forecast_pivot

    # 显示数据加载信息
    df = st.session_state['df_processed']
    st.metric("数据行数", f"{len(df):,}")
    st.metric("品类数量", f"{df['类目'].nunique()}")
    st.metric("国家/站点", f"{df['国家'].nunique()}")

    st.markdown("---")

    # ============================================================
    # 筛选器
    # ============================================================
    st.markdown("### 🔍 数据筛选")

    # 国家筛选
    all_countries = ['全部'] + sorted(df['国家'].dropna().unique().tolist())
    selected_country = st.selectbox("🌍 国家/站点", all_countries, index=0, key='country')

    # 品类筛选
    if selected_country == '全部':
        df_filtered_country = df.copy()
    else:
        df_filtered_country = df[df['国家'] == selected_country]

    all_categories = ['全部'] + sorted(df_filtered_country['类目'].dropna().unique().tolist())
    selected_category = st.selectbox("📦 产品品类", all_categories, index=0, key='category')

    # 年份筛选
    all_years = [2024, 2025, 2026]
    selected_years = st.multiselect("📅 年份筛选", all_years, default=[2025, 2026], key='year_filter')

    # 月份筛选
    all_months = list(range(3, 8))  # 3-7月
    selected_months = st.multiselect("📅 月份筛选", all_months, default=all_months, format_func=lambda x: f"{x}月", key='month_filter')

    # SKU精准筛选
    df_for_sku_filter = df_filtered_country.copy()
    if selected_category != '全部':
        df_for_sku_filter = df_for_sku_filter[df_for_sku_filter['类目'] == selected_category].copy()

    # 获取可用的SKU选项（如果有SKU列则使用，否则使用FNSKU）
    if 'SKU' in df_for_sku_filter.columns:
        sku_column = 'SKU'
    else:
        sku_column = 'FNSKU'

    all_skus = ['全部'] + sorted(df_for_sku_filter[sku_column].dropna().unique().tolist())
    selected_skus = st.multiselect("🏷️ SKU筛选", all_skus, default=['全部'], key='sku_filter')

    st.markdown("---")

    # 重新加载数据按钮
    if st.button("🔄 重新加载数据", use_container_width=True, key='reload_data'):
        if 'df_processed' in st.session_state:
            del st.session_state['df_processed']
            del st.session_state['df_market']
            if 'df_forecast_monthly' in st.session_state:
                del st.session_state['df_forecast_monthly']
            if 'df_forecast_pivot' in st.session_state:
                del st.session_state['df_forecast_pivot']
        st.rerun()

# ============================================================
# 主容器：数据展示
# ============================================================
st.markdown("# 实际销量与预测趋势对比分析")
st.markdown("---")

# 检查是否有处理后的数据
if 'df_processed' not in st.session_state:
    st.markdown("""
    <div style='text-align: center; padding: 60px 20px;'>
        <h3 style='color: #0366d6;'>⚠️ 数据加载失败</h3>
        <p style='color: #586069; font-size: 16px;'>请确保以下数据文件已放置在项目目录中：</p>
        <ul style='text-align: left; color: #586069;'>
            <li>1️⃣ 销量统计.xlsx</li>
            <li>2️⃣ 产品运营信息表.xlsx</li>
            <li>3️⃣ 销量预测.xlsx</li>
            <li>4️⃣ 大盘趋势表.xlsx</li>
        </ul>
        <p style='color: #586069; font-size: 14px;'>支持格式：.xlsx, .xls, .csv</p>
    </div>
    """, unsafe_allow_html=True)
else:
    df = st.session_state['df_processed']

    # 获取筛选条件
    selected_country = st.session_state.get('country', '全部')
    selected_category = st.session_state.get('category', '全部')
    selected_skus = st.session_state.get('sku_filter', ['全部'])

    # 应用筛选
    if selected_country == '全部':
        df_display = df.copy()
    else:
        df_display = df[df['国家'] == selected_country]

    if selected_category != '全部':
        df_display = df_display[df_display['类目'] == selected_category]

    # SKU筛选
    if '全部' not in selected_skus and len(selected_skus) > 0:
        # 确定SKU列名（优先使用SKU，其次使用FNSKU）
        sku_column = 'SKU' if 'SKU' in df_display.columns else 'FNSKU'
        # 过滤销量数据
        df_display = df_display[df_display[sku_column].isin(selected_skus)]

    # 显示筛选条件概览
    col1, col2 = st.columns(2)
    with col1:
        st.metric("国家", selected_country if selected_country != '全部' else '全部')
    with col2:
        st.metric("品类", selected_category if selected_category != '全部' else '全部')

    st.markdown("---")

    # ============================================================
    # 核心图表区域：瀑布流布局（一品线一图）
    # ============================================================

    # 获取筛选参数
    selected_years = st.session_state.get('year_filter', [2025, 2026])
    selected_months = st.session_state.get('month_filter', list(range(3, 8)))

    # 确定要显示的品类列表
    if selected_category == '全部':
        # 显示所有品类
        if selected_country == '全部':
            display_categories = df['类目'].dropna().unique().tolist()
        else:
            df_filtered_country = df[df['国家'] == selected_country]
            display_categories = df_filtered_country['类目'].dropna().unique().tolist()
        display_categories = sorted(display_categories)
    else:
        # 显示选中品类
        display_categories = [selected_category]

    if len(display_categories) > 0 and len(df_display) > 0:
        # 获取市场数据和预测数据
        df_market = st.session_state.get('df_market', None)
        df_forecast_pivot = st.session_state.get('df_forecast_pivot', None)
        df_forecast_monthly = st.session_state.get('df_forecast_monthly', None)

        # 使用瀑布流布局展示所有品类图表
        num_cols = 2  # 每行2个品类图表

        for idx, category in enumerate(display_categories):
            # 计算行列位置
            row_num = idx // num_cols
            col_num = idx % num_cols

            # 为每个品类创建独立的图表区域
            if col_num == 0:
                cols = st.columns(2)

            with cols[col_num]:
                st.markdown(f"#### 📊 {category}")

                # 获取该品类的聚合数据
                if selected_country == '全部':
                    cat_df = df[df['类目'] == category].copy()
                else:
                    cat_df = df[(df['国家'] == selected_country) & (df['类目'] == category)].copy()

                if len(cat_df) > 0:
                    # 按类目聚合历史销量数据
                    agg_row = cat_df.select_dtypes(include='number').sum()
                    agg_row['类目'] = category
                    agg_row['国家'] = selected_country

                    # 获取预测数据：根据是否选择了SKU决定使用哪种数据
                    if '全部' not in selected_skus and len(selected_skus) > 0 and df_forecast_monthly is not None:
                        # SKU筛选模式：仅使用选中SKU的预测数据
                        # 确定FNSKU列表（用于过滤预测数据）
                        fnsku_list = cat_df['FNSKU'].dropna().unique().tolist()
                        df_forecast_filtered = df_forecast_monthly[
                            df_forecast_monthly['FNSKU'].isin(fnsku_list)
                        ]
                        # 按类目重新聚合预测数据
                        df_forecast_by_cat = df_forecast_filtered.groupby('预测月份')['预测销量'].sum().reset_index()
                        # 转换为透视表格式
                        forecast_pivot_filtered = df_forecast_by_cat.pivot(
                            index='预测月份',
                            columns=None,
                            values='预测销量'
                        ).reset_index()
                        forecast_pivot_filtered.columns.name = None
                        forecast_pivot_filtered.columns = ['预测月份', '预测销量']

                        # 合并预测数据到 agg_row
                        for month in range(3, 8):  # 3-7月
                            month_key = f'2026-{month:02d}'
                            forecast_val = forecast_pivot_filtered[
                                forecast_pivot_filtered['预测月份'] == month_key
                            ]['预测销量']
                            if len(forecast_val) > 0:
                                agg_row[f'预测_{month_key}'] = forecast_val.values[0]
                            else:
                                agg_row[f'预测_{month_key}'] = 0
                    elif df_forecast_pivot is not None:
                        # 非SKU筛选模式：使用类目级预测数据
                        forecast_row = df_forecast_pivot[df_forecast_pivot['类目'] == category]
                        if len(forecast_row) > 0:
                            # 将预测数据添加到 agg_row
                            for col in forecast_row.columns:
                                if col != '类目':
                                    agg_row[col] = forecast_row[col].values[0]
                        else:
                            # 如果预测表中没有该品类，将预测列设为0
                            for month in range(3, 8):  # 3-7月
                                agg_row[f'预测_2026-{month:02d}'] = 0

                    # 执行 AI 算法
                    seasonal_result = algorithm_a_seasonal_analysis(agg_row)
                    risk_result = algorithm_b_risk_assessment(agg_row)

                    # 筛选并转换市场数据
                    df_market_filtered = get_market_data_for_selection(df_market, selected_country, category)
                    market_year_data = transform_market_data_for_chart(df_market_filtered)

                    # 创建双 Y 轴图表（传入筛选参数）
                    fig = create_dual_axis_trend_chart(
                        agg_row, market_year_data, seasonal_result, category,
                        selected_years, selected_months
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # 显示简化的 AI 诊断信息
                    with st.expander("🤖 AI 诊断", expanded=False):
                        st.write(f"{risk_result['diagnosis']}")
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("偏差率", f"{risk_result['deviation_rate']:+.1f}%")
                        with col_b:
                            st.metric("预测销量", f"{int(risk_result['forecast_total']):,}")
                        with col_c:
                            st.metric("加权基准", f"{int(risk_result['weighted_baseline']):,}")
                else:
                    st.info(f"📌 {category} 无数据")
    else:
        st.info("📌 请选择筛选条件以查看分析结果")

    st.markdown("---")

    # ============================================================
    # 数据表格展示
    # ============================================================
    with st.expander("📋 底层数据详情", expanded=False):
        display_cols = [
            'FNSKU', 'SKU名称', '国家', '类目', '品牌',
            '主推标签', '利润标签', 'Listing定位'
        ]
        history_cols = [col for col in df.columns if re.match(r'2025-0[7-9]|2025-1[0-2]|2026-0[1-2]', col)]
        display_cols.extend(history_cols)
        forecast_cols = [col for col in df.columns if '预测' in col]
        display_cols.extend(forecast_cols)
        display_cols = [col for col in display_cols if col in df_display.columns]

        st.dataframe(
            df_display[display_cols],
            use_container_width=True,
            height=400,
            hide_index=True
        )

# ============================================================
# 底部版权信息
# ============================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #586069;'>"
    "© 2026 智能备货分析看板 | 数据驱动决策 | AI 算法驱动</div>",
    unsafe_allow_html=True
)
