import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

# --- 1. 网页全局设置 ---
st.set_page_config(page_title="AI 驱动销量趋势与预测看板", layout="wide", page_icon="🤖")
st.title("🤖 AI 驱动销量趋势与预测智能看板 (V4.0)")
st.markdown("新增 **生命周期筛选**、**历史均值基准**、**淡旺季自动标注** 与 **AI 预测诊断**。")

# --- 2. 侧边栏：文件上传 ---
with st.sidebar:
    st.header("📁 1. 数据配置区")
    file_sales = st.file_uploader("拖拽上传【销量统计】表格", type=['csv', 'xlsx'])
    file_forecast = st.file_uploader("拖拽上传【销量预测】表格", type=['csv', 'xlsx'])
    
    st.markdown("---")
    st.header("🔍 2. 全局基础筛选")
    country_filter = st.empty()
    category_filter = st.empty()
    
    st.markdown("---")
    st.header("💡 3. 生命周期/定位")
    lifecycle_filter = st.empty()

# --- 3. 核心运算逻辑 ---
if file_sales is not None and file_forecast is not None:
    try:
        with st.spinner('🚀 正在进行 AI 数据清洗、标注提取与均值偏离度计算...'):
            df_sales = pd.read_csv(file_sales) if file_sales.name.endswith('csv') else pd.read_excel(file_sales)
            df_forecast = pd.read_csv(file_forecast) if file_forecast.name.endswith('csv') else pd.read_excel(file_forecast)

            # 数据提取与清洗
            hist_cols = [c for c in df_sales.columns if str(c).startswith('2024') or str(c).startswith('2025') or str(c).startswith('2026-01') or str(c).startswith('2026-02')]
            df_sales[hist_cols] = df_sales[hist_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            df_sales['二级分类'] = df_sales['二级分类'].fillna('不成类目')
            df_sales['国家'] = df_sales['国家'].fillna('未知')
            df_sales['标签'] = df_sales['标签'].fillna('未知标签')
            
            # --- 提取生命周期标签池 ---
            # 简单切分并提取核心特征词汇 (包含主推, 老, 新, 清货, 正常等)
            all_tags_raw = ','.join(df_sales['标签'].tolist()).split(',')
            core_tags = [t.strip() for t in all_tags_raw if t.strip() in ['主推款', '非主推款', '新listing', '老listing', '清货在售', '正常在售', '维稳']]
            unique_tags = list(set(core_tags)) if core_tags else ['无标准标签']
            
            valid_sales_categories = df_sales['二级分类'].unique().tolist()

            # 预测表处理
            if '品线' in df_forecast.columns:
                df_forecast['二级分类'] = df_forecast['品线']
            else:
                fnsku_cat_map = df_sales.groupby('FNSKU')['二级分类'].first().to_dict()
                df_forecast['二级分类'] = df_forecast['FNSKU'].map(fnsku_cat_map)
            df_forecast['二级分类'] = df_forecast['二级分类'].apply(lambda x: x if x in valid_sales_categories else '不成类目')
            
            if '国家' not in df_forecast.columns:
                fnsku_country_map = df_sales.groupby('FNSKU')['国家'].first().to_dict()
                df_forecast['国家'] = df_forecast['FNSKU'].map(fnsku_country_map).fillna('未知')

            fc_cols = ['2026-03', '2026-04', '2026-05', '2026-06', '2026-07']
            for col in fc_cols:
                if col not in df_forecast.columns:
                    week_cols = [c for c in df_forecast.columns if c.startswith(col)]
                    df_forecast[col] = df_forecast[week_cols].sum(axis=1) if week_cols else 0
            df_forecast[fc_cols] = df_forecast[fc_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

            # --- 侧边栏交互 ---
            all_countries = sorted(list(set(df_sales['国家'].unique()) | set(df_forecast['国家'].unique())))
            all_countries.insert(0, '全球 (全部站点)')
            selected_country = country_filter.selectbox("🌍 切换国家/站点", all_countries)
            
            if selected_country != '全球 (全部站点)':
                df_sales = df_sales[df_sales['国家'] == selected_country]
                df_forecast = df_forecast[df_forecast['国家'] == selected_country]
            
            selected_lifecycles = lifecycle_filter.multiselect("🏷️ 按产品定位筛选 (空为不过滤)", unique_tags, default=[])
            
            # 如果选择了生命周期，依据标签过滤SKU
            if selected_lifecycles:
                pattern = '|'.join(selected_lifecycles)
                df_sales = df_sales[df_sales['标签'].str.contains(pattern, na=False)]
                valid_fnskus = df_sales['FNSKU'].unique().tolist()
                df_forecast = df_forecast[df_forecast['FNSKU'].isin(valid_fnskus)]

            all_categories = sorted(df_sales['二级分类'].unique().tolist())
            selected_cats = category_filter.multiselect("📑 筛选核心品线", all_categories, default=all_categories[:10] if len(all_categories)>10 else all_categories)
            
            if not selected_cats:
                st.warning("⚠️ 请在左侧选择至少一个品线与标签组合！")
                st.stop()
                
            df_sales_filtered = df_sales[df_sales['二级分类'].isin(selected_cats)]
            df_forecast_filtered = df_forecast[df_forecast['二级分类'].isin(selected_cats)]

            hist_cat_sales = df_sales_filtered.groupby('二级分类')[hist_cols].sum()
            forecast_cat_sales = df_forecast_filtered.groupby('二级分类')[fc_cols].sum()
            combined_cat_sales = pd.concat([hist_cat_sales, forecast_cat_sales], axis=1).fillna(0)
            categories = combined_cat_sales.sum(axis=1).sort_values(ascending=False).index.tolist()

            st.markdown("---")
            months = [f"{i:02d}" for i in range(1, 13)]

            # --- 生成独立的品线卡片 (包含图表与诊断) ---
            for cat in categories:
                st.markdown(f"### 📦 品线：{cat}")
                
                row_data = combined_cat_sales.loc[cat]
                y2024 = [row_data.get(f"2024-{m}", 0) for m in months]
                y2025 = [row_data.get(f"2025-{m}", 0) for m in months]
                y2026_act = [row_data.get(f"2026-{m}", np.nan) if m in ['01', '02'] else np.nan for m in months]
                
                y2026_pred = [np.nan] * 12
                y2026_pred[1] = row_data.get("2026-02", np.nan)
                for j, m in enumerate(['03', '04', '05', '06', '07']):
                    y2026_pred[j+2] = row_data.get(f"2026-{m}", np.nan)

                # --- 计算历史均值与峰谷 ---
                valid_history = [v for v in y2024 + y2025 if v > 0]
                hist_mean = np.mean(valid_history) if valid_history else 0
                
                # 寻找峰谷 (基于24和25年的综合趋势)
                avg_trend = [(y2024[i] + y2025[i])/2 for i in range(12)]
                peak_idx = np.argmax(avg_trend)
                trough_idx = np.argmin(avg_trend)
                
                # --- AI 智能预测诊断逻辑 ---
                pred_values = [row_data.get(f"2026-{m}", 0) for m in ['03', '04', '05', '06', '07']]
                pred_mean = np.mean(pred_values) if pred_values else 0
                
                diag_msg = ""
                if hist_mean == 0:
                    diag_msg = "🆕 缺乏历史数据，建议根据【新listing】起盘计划评估预测。"
                else:
                    deviation = (pred_mean - hist_mean) / hist_mean * 100
                    if deviation > 20:
                        diag_msg = f"⚠️ **【高估/高预期预警】** 预测均值大幅超历史水准 (+{deviation:.1f}%)。若包含【老listing/清货款】，极易造成滞销；若为【主推款】，请确保广告预算充足以支撑此增量。"
                    elif deviation < -20:
                        diag_msg = f"🚨 **【低估/断货预警】** 预测均值远低历史水准 ({deviation:.1f}%)。请检查是否受竞品压制或库存受限？若是【老listing】平稳期，可能错失接下来几个月的自然流量。"
                    else:
                        diag_msg = f"✅ **【走势平稳】** 预测值围绕历史均值波动 (偏差 {deviation:.1f}%)，备货风险较低。"

                # --- 渲染图表 ---
                fig = go.Figure()
                
                # 画基准线
                fig.add_hline(y=hist_mean, line_dash="dash", line_color="gray", annotation_text=f"历史月均线: {int(hist_mean)}", annotation_position="top left")

                fig.add_trace(go.Scatter(x=months, y=y2024, mode='lines', name='2024 实际', line=dict(color='#1f77b4', width=2), hovertemplate='2024: %{y:,.0f}'))
                fig.add_trace(go.Scatter(x=months, y=y2025, mode='lines', name='2025 实际', line=dict(color='#2ca02c', width=2), hovertemplate='2025: %{y:,.0f}'))
                fig.add_trace(go.Scatter(x=months, y=y2026_act, mode='lines+markers', name='2026 实际', line=dict(color='#ff7f0e', width=3)))
                fig.add_trace(go.Scatter(x=months, y=y2026_pred, mode='lines+markers', name='2026 预测', line=dict(color='#ff7f0e', width=3, dash='dash')))

                # 标注峰谷
                fig.add_annotation(x=months[peak_idx], y=max(y2024[peak_idx], y2025[peak_idx]), text="🔴 旺季峰值", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="red")
                fig.add_annotation(x=months[trough_idx], y=min(y2024[trough_idx], y2025[trough_idx]), text="🟢 淡季低谷", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="green", ay=40)

                fig.update_layout(height=350, margin=dict(t=20, b=10, l=10, r=10), hovermode='x unified', plot_bgcolor='white', legend=dict(orientation="h", y=1.05, x=0))
                fig.update_xaxes(type='category', showgrid=True, gridcolor='WhiteSmoke')
                fig.update_yaxes(showgrid=True, gridcolor='WhiteSmoke')

                # 在页面展示：左侧图表，右侧诊断卡片
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    st.info("💡 **AI 趋势诊断**")
                    st.write(diag_msg)
                    st.write(f"**历史综合淡季**: {months[trough_idx]} 月")
                    st.write(f"**历史综合旺季**: {months[peak_idx]} 月")
                
                st.markdown("---")

    except Exception as e:
        st.error(f"❌ 数据处理出错，请确认表格字段完整。详细错误：{e}")
else:
    st.info("👈 请在左侧上传数据文件以启用 AI 诊断系统。")
