import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

# --- 1. 网页全局设置 ---
st.set_page_config(page_title="动态销量趋势与预测看板", layout="wide", page_icon="📈")
st.title("📊 销量趋势与预测看板")

# --- 2. 侧边栏：文件上传 ---
with st.sidebar:
    st.header("📁 1. 数据配置区")
    file_sales = st.file_uploader("拖拽上传【销量统计】表格", type=['csv', 'xlsx'])
    file_forecast = st.file_uploader("拖拽上传【销量预测】表格", type=['csv', 'xlsx'])
    
    st.markdown("---")
    st.header("🔍 2. 全局筛选器")
    country_filter = st.empty()
    category_filter = st.empty()

# --- 3. 核心运算与渲染逻辑 ---
if file_sales is not None and file_forecast is not None:
    try:
        with st.spinner('🚀 正在为您拼命清洗和计算数据，请稍候...'):
            # --- 读取数据 ---
            df_sales = pd.read_csv(file_sales) if file_sales.name.endswith('csv') else pd.read_excel(file_sales)
            df_forecast = pd.read_csv(file_forecast) if file_forecast.name.endswith('csv') else pd.read_excel(file_forecast)

            # --- 清洗历史销量 (销量统计) ---
            hist_cols = [c for c in df_sales.columns if str(c).startswith('2024') or str(c).startswith('2025') or str(c).startswith('2026-01') or str(c).startswith('2026-02')]
            df_sales[hist_cols] = df_sales[hist_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            df_sales['二级分类'] = df_sales['二级分类'].fillna('不成类目')
            df_sales['国家'] = df_sales['国家'].fillna('未知')
            
            # 提取销量统计中合法的二级分类池
            valid_sales_categories = df_sales['二级分类'].unique().tolist()

            # --- 清洗预测销量 (销量预测) ---
            # 1. 统一品线命名 (优先读取"品线"列，若无则靠FNSKU映射)
            if '品线' in df_forecast.columns:
                df_forecast['二级分类'] = df_forecast['品线']
            else:
                fnsku_cat_map = df_sales.groupby('FNSKU')['二级分类'].first().to_dict()
                df_forecast['二级分类'] = df_forecast['FNSKU'].map(fnsku_cat_map)
                
            # 核心需求：预测多了的品线，纳入"不成类目"
            df_forecast['二级分类'] = df_forecast['二级分类'].apply(lambda x: x if x in valid_sales_categories else '不成类目')
            
            # 2. 统一国家命名 (优先读取"国家"列，若无则靠FNSKU映射)
            if '国家' not in df_forecast.columns:
                fnsku_country_map = df_sales.groupby('FNSKU')['国家'].first().to_dict()
                df_forecast['国家'] = df_forecast['FNSKU'].map(fnsku_country_map).fillna('未知')

            # 3. 提取预测月份数据 (兼容按月直接给定 or 按周累加)
            fc_cols = ['2026-03', '2026-04', '2026-05', '2026-06', '2026-07']
            for col in fc_cols:
                if col not in df_forecast.columns:
                    # 如果没有直接的月份列，尝试把包含该月份的周累加
                    week_cols = [c for c in df_forecast.columns if c.startswith(col)]
                    df_forecast[col] = df_forecast[week_cols].sum(axis=1) if week_cols else 0
            df_forecast[fc_cols] = df_forecast[fc_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

            # --- 侧边栏：动态筛选器生成 ---
            # 合并两表的国家，生成下拉菜单
            all_countries = sorted(list(set(df_sales['国家'].dropna().unique()) | set(df_forecast['国家'].dropna().unique())))
            all_countries.insert(0, '全球 (全部站点)')
            selected_country = country_filter.selectbox("🌍 切换国家/站点", all_countries)
            
            # 根据国家过滤数据
            if selected_country != '全球 (全部站点)':
                df_sales_filtered = df_sales[df_sales['国家'] == selected_country]
                df_forecast_filtered = df_forecast[df_forecast['国家'] == selected_country]
            else:
                df_sales_filtered = df_sales
                df_forecast_filtered = df_forecast
                
            # 品类多选器
            all_categories = sorted(df_sales_filtered['二级分类'].unique().tolist())
            selected_cats = category_filter.multiselect("📑 筛选核心品线 (默认全选)", all_categories, default=all_categories)
            
            if not selected_cats:
                st.warning("⚠️ 请至少在左侧选择一个品线进行分析！")
                st.stop()
                
            df_sales_filtered = df_sales_filtered[df_sales_filtered['二级分类'].isin(selected_cats)]
            df_forecast_filtered = df_forecast_filtered[df_forecast_filtered['二级分类'].isin(selected_cats)]

            # --- 聚合数据 ---
            hist_cat_sales = df_sales_filtered.groupby('二级分类')[hist_cols].sum()
            forecast_cat_sales = df_forecast_filtered.groupby('二级分类')[fc_cols].sum()
            combined_cat_sales = pd.concat([hist_cat_sales, forecast_cat_sales], axis=1).fillna(0)
            
            # --- 顶部 KPI 卡片计算 ---
            st.markdown("### 🎯 核心业务概览 (3月-7月预测期对比)")
            kpi_cols = st.columns(4)
            
            # 计算 2025年 3-7月 总量 vs 2026年 3-7月 总量
            months_3_to_7 = ['03', '04', '05', '06', '07']
            sales_25_target = combined_cat_sales[[f'2025-{m}' for m in months_3_to_7]].sum().sum()
            sales_26_target = combined_cat_sales[[f'2026-{m}' for m in months_3_to_7]].sum().sum()
            
            yoy_growth = ((sales_26_target - sales_25_target) / sales_25_target * 100) if sales_25_target > 0 else 0
            
            kpi_cols[0].metric("2025年同期实际销量 (3-7月)", f"{int(sales_25_target):,}")
            kpi_cols[1].metric("2026年预测总销量 (3-7月)", f"{int(sales_26_target):,}", f"{yoy_growth:.1f}% 同比预期")
            
            sales_24_total = combined_cat_sales[[f'2024-{m}' for m in [f"{i:02d}" for i in range(1, 13)]]].sum().sum()
            sales_25_total = combined_cat_sales[[f'2025-{m}' for m in [f"{i:02d}" for i in range(1, 13)]]].sum().sum()
            kpi_cols[2].metric("2024年全盘销量", f"{int(sales_24_total):,}")
            kpi_cols[3].metric("2025年全盘销量", f"{int(sales_25_total):,}", f"{((sales_25_total-sales_24_total)/sales_24_total*100):.1f}% 同比" if sales_24_total>0 else "")

            st.markdown("---")

            # --- 生成动态 Plotly 看板 ---
            categories = combined_cat_sales.sum(axis=1).sort_values(ascending=False).index.tolist()
            num_cats = len(categories)
            cols = 2
            rows = math.ceil(num_cats / cols)

            fig = make_subplots(rows=rows, cols=cols, subplot_titles=categories, vertical_spacing=0.04, horizontal_spacing=0.05)
            months = [f"{i:02d}" for i in range(1, 13)]

            for i, cat in enumerate(categories):
                r = i // cols + 1
                c = i % cols + 1
                row_data = combined_cat_sales.loc[cat]
                
                y2024 = [row_data.get(f"2024-{m}", np.nan) for m in months]
                y2025 = [row_data.get(f"2025-{m}", np.nan) for m in months]
                y2026_act = [row_data.get(f"2026-{m}", np.nan) if m in ['01', '02'] else np.nan for m in months]
                
                # 预测折线处理
                y2026_pred = [np.nan] * 12
                y2026_pred[1] = row_data.get("2026-02", np.nan) # 起点连接 2月份实际
                for j, m in enumerate(['03', '04', '05', '06', '07']):
                    y2026_pred[j+2] = row_data.get(f"2026-{m}", np.nan)
                    
                show_legend = True if i == 0 else False 
                    
                fig.add_trace(go.Scatter(x=months, y=y2024, mode='lines+markers', name='2024 实际', 
                                         line=dict(color='#1f77b4', width=2), showlegend=show_legend,
                                         hovertemplate='%{y:,.0f}<extra>2024年</extra>'), row=r, col=c)
                fig.add_trace(go.Scatter(x=months, y=y2025, mode='lines+markers', name='2025 实际', 
                                         line=dict(color='#2ca02c', width=2), showlegend=show_legend,
                                         hovertemplate='%{y:,.0f}<extra>2025年</extra>'), row=r, col=c)
                fig.add_trace(go.Scatter(x=months, y=y2026_act, mode='lines+markers', name='2026 实际(1-2月)', 
                                         line=dict(color='#ff7f0e', width=2), showlegend=show_legend,
                                         hovertemplate='%{y:,.0f}<extra>2026年实际</extra>'), row=r, col=c)
                fig.add_trace(go.Scatter(x=months, y=y2026_pred, mode='lines+markers', name='2026 预测(3-7月)', 
                                         line=dict(color='#ff7f0e', width=2, dash='dash'), showlegend=show_legend,
                                         hovertemplate='%{y:,.0f}<extra>2026年预测</extra>'), row=r, col=c)

                fig.update_xaxes(type='category', title_text="", row=r, col=c, showgrid=True, gridcolor='WhiteSmoke')
                fig.update_yaxes(title_text="", row=r, col=c, showgrid=True, gridcolor='WhiteSmoke')

            # 整体UI样式高度自适应
            fig.update_layout(height=400 * rows, hovermode='x unified', plot_bgcolor='white', margin=dict(t=30, l=10, r=10, b=10),
                              legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5))

            st.plotly_chart(fig, use_container_width=True)

            # --- 底层数据下载 ---
            with st.expander("📥 点击查看或下载当前视图的底层聚合数据"):
                st.dataframe(combined_cat_sales)
                csv = combined_cat_sales.to_csv(encoding='utf-8-sig')
                st.download_button("导出 CSV", data=csv, file_name='dashboard_filtered_data.csv', mime='text/csv')

    except Exception as e:
        st.error(f"❌ 数据处理出错，请检查上传的表格是否包含必需的月份字段。详细错误：{e}")

else:

    st.info("👈 **第一步：** 请在左侧侧边栏将您的《销量统计》和《销量预测》表格拖拽入框中。系统将在 2 秒内为您渲染完整视图！")
