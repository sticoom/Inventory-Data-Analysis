import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

# --- 1. 网页全局设置 ---
st.set_page_config(page_title="AI 销量趋势与风险诊断看板", layout="wide", page_icon="📈")
st.title("📈 销量趋势与 AI 风险诊断看板 (V5.0 终极版)")
st.markdown("集成 **3个月滑动平均淡旺季测算**、**3:7加权历史基准** 与 **定位&SKU级联筛选**，辅助精准备货。")

# --- 2. 侧边栏：文件上传 ---
with st.sidebar:
    st.header("📁 1. 数据配置区")
    file_sales = st.file_uploader("拖拽上传【销量统计】", type=['csv', 'xlsx'])
    file_forecast = st.file_uploader("拖拽上传【销量预测】", type=['csv', 'xlsx'])
    
    st.markdown("---")
    st.header("🔍 全局级联筛选器")
    country_filter = st.empty()
    category_filter = st.empty()
    position_filter = st.empty()
    sku_filter = st.empty()

# --- 核心目标定位词库 ---
TARGET_POSITIONS = ['待上架', '流量款', '清货款', '利润款', '普通款', '需维护', '停售', '主推款']

def extract_position_tags(tag_string):
    """正则提取产品定位标签"""
    if pd.isna(tag_string):
        return []
    found = [p for p in TARGET_POSITIONS if p in str(tag_string)]
    return found if found else ['未打标']

# --- 3. 核心运算逻辑 ---
if file_sales is not None and file_forecast is not None:
    try:
        with st.spinner('🤖 AI 正在进行多维度数据洗盘、滑动平均计算与风险排雷...'):
            # --- 数据读取 ---
            df_sales = pd.read_csv(file_sales) if file_sales.name.endswith('csv') else pd.read_excel(file_sales)
            df_forecast = pd.read_csv(file_forecast) if file_forecast.name.endswith('csv') else pd.read_excel(file_forecast)

            # --- 清洗销量统计表 ---
            hist_cols = [c for c in df_sales.columns if str(c).startswith('2024') or str(c).startswith('2025') or str(c).startswith('2026-01') or str(c).startswith('2026-02')]
            df_sales[hist_cols] = df_sales[hist_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            df_sales['二级分类'] = df_sales['二级分类'].fillna('不成类目')
            df_sales['国家'] = df_sales['国家'].fillna('未知')
            df_sales['SKU'] = df_sales['SKU'].fillna('未知SKU')
            
            # 提取产品定位并展开（为了能支持多选过滤）
            df_sales['定位标签列表'] = df_sales['标签'].apply(extract_position_tags)
            
            valid_sales_categories = df_sales['二级分类'].unique().tolist()

            # --- 清洗预测销量表 ---
            # 构建 FNSKU 到各个字段的映射桥梁
            fnsku_map = df_sales.set_index('FNSKU')[['二级分类', '国家', 'SKU', '定位标签列表']].to_dict('index')
            
            # 填补品线
            if '品线' in df_forecast.columns:
                df_forecast['二级分类'] = df_forecast['品线']
            else:
                df_forecast['二级分类'] = df_forecast['FNSKU'].map(lambda x: fnsku_map.get(x, {}).get('二级分类', '不成类目'))
            df_forecast['二级分类'] = df_forecast['二级分类'].apply(lambda x: x if x in valid_sales_categories else '不成类目')
            
            # 填补国家、SKU与定位标签
            df_forecast['国家'] = df_forecast.get('国家', df_forecast['FNSKU'].map(lambda x: fnsku_map.get(x, {}).get('国家', '未知')))
            df_forecast['SKU'] = df_forecast['FNSKU'].map(lambda x: fnsku_map.get(x, {}).get('SKU', '未知SKU'))
            df_forecast['定位标签列表'] = df_forecast['FNSKU'].map(lambda x: fnsku_map.get(x, {}).get('定位标签列表', ['未打标']))

            # 聚合预测月份
            fc_cols = ['2026-03', '2026-04', '2026-05', '2026-06', '2026-07']
            for col in fc_cols:
                if col not in df_forecast.columns:
                    week_cols = [c for c in df_forecast.columns if c.startswith(col)]
                    df_forecast[col] = df_forecast[week_cols].sum(axis=1) if week_cols else 0
            df_forecast[fc_cols] = df_forecast[fc_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

            # --- 侧边栏级联交互 ---
            # 1. 国家
            all_countries = ['全球 (全部站点)'] + sorted(list(set(df_sales['国家'].unique()) | set(df_forecast['国家'].unique())))
            selected_country = country_filter.selectbox("🌍 1. 国家/站点筛选", all_countries)
            
            if selected_country != '全球 (全部站点)':
                df_sales = df_sales[df_sales['国家'] == selected_country]
                df_forecast = df_forecast[df_forecast['国家'] == selected_country]
            
            # 2. 品线
            all_categories = sorted(df_sales['二级分类'].unique().tolist())
            selected_cats = category_filter.multiselect("📑 2. 品线筛选 (默认全选)", all_categories, default=all_categories[:5] if len(all_categories)>5 else all_categories)
            if selected_cats:
                df_sales = df_sales[df_sales['二级分类'].isin(selected_cats)]
                df_forecast = df_forecast[df_forecast['二级分类'].isin(selected_cats)]
                
            # 3. 产品定位 (打平列表后提取唯一值)
            all_positions = sorted(list(set([tag for tags in df_sales['定位标签列表'] for tag in tags])))
            selected_positions = position_filter.multiselect("💡 3. 产品定位筛选", all_positions, default=[])
            if selected_positions:
                # 只要包含选中定位之一即可
                df_sales = df_sales[df_sales['定位标签列表'].apply(lambda x: any(p in x for p in selected_positions))]
                df_forecast = df_forecast[df_forecast['定位标签列表'].apply(lambda x: any(p in x for p in selected_positions))]

            # 4. SKU 动态级联
            all_skus = sorted(df_sales['SKU'].unique().tolist())
            selected_skus = sku_filter.multiselect(f"📦 4. SKU精准下钻 (当前可选 {len(all_skus)} 个)", all_skus, default=[])
            if selected_skus:
                df_sales = df_sales[df_sales['SKU'].isin(selected_skus)]
                df_forecast = df_forecast[df_forecast['SKU'].isin(selected_skus)]

            # --- 动态决定分析维度 (品线还是SKU) ---
            group_col = 'SKU' if selected_skus else '二级分类'
            
            hist_grouped = df_sales.groupby(group_col)[hist_cols].sum()
            forecast_grouped = df_forecast.groupby(group_col)[fc_cols].sum()
            combined_data = pd.concat([hist_grouped, forecast_grouped], axis=1).fillna(0)
            analysis_items = combined_data.sum(axis=1).sort_values(ascending=False).index.tolist()

            st.markdown("---")
            months = [f"{i:02d}" for i in range(1, 13)]

            # --- 生成瀑布流卡片 ---
            for item in analysis_items:
                row_data = combined_data.loc[item]
                y2024 = [row_data.get(f"2024-{m}", 0) for m in months]
                y2025 = [row_data.get(f"2025-{m}", 0) for m in months]
                y2026_act = [row_data.get(f"2026-{m}", np.nan) if m in ['01', '02'] else np.nan for m in months]
                
                y2026_pred = [np.nan] * 12
                y2026_pred[1] = row_data.get("2026-02", np.nan)
                for j, m in enumerate(['03', '04', '05', '06', '07']):
                    y2026_pred[j+2] = row_data.get(f"2026-{m}", np.nan)

                # --- 算法1：历史全盘均值与极致极小点 ---
                hist_24_25 = y2024 + y2025
                valid_hist = [v for v in hist_24_25 if v > 0]
                hist_mean = np.mean(valid_hist) if valid_hist else 0
                
                max_val = max(hist_24_25) if hist_24_25 else 0
                min_val = min(hist_24_25) if hist_24_25 else 0
                max_idx = hist_24_25.index(max_val) if hist_24_25 else 0
                min_idx = hist_24_25.index(min_val) if hist_24_25 else 0
                
                max_year, max_month = ("2024", months[max_idx]) if max_idx < 12 else ("2025", months[max_idx-12])
                min_year, min_month = ("2024", months[min_idx]) if min_idx < 12 else ("2025", months[min_idx-12])

                # --- 算法2：3个月滑动平均找综合淡旺季 ---
                avg_monthly = [(y2024[i] + y2025[i])/2 for i in range(12)]
                rolling_3 = []
                for i in range(12):
                    prev_m = avg_monthly[i-1] # python 负数索引巧妙解决12月跨年
                    curr_m = avg_monthly[i]
                    next_m = avg_monthly[(i+1)%12]
                    rolling_3.append((prev_m + curr_m + next_m) / 3)
                
                best_m_idx = np.argmax(rolling_3)
                worst_m_idx = np.argmin(rolling_3)
                
                def format_season(idx):
                    return f"{12 if idx==0 else idx}月~{(idx+2)%12 if (idx+2)%12!=0 else 12}月"
                
                best_season = format_season(best_m_idx)
                worst_season = format_season(worst_m_idx)

                # --- 算法3：0.7/0.3 比例加权计算偏离度与排雷 ---
                sum_pred_3_7 = sum(y2026_pred[2:7])
                sum_25_3_7 = sum(y2025[2:7])
                sum_24_3_7 = sum(y2024[2:7])
                
                weighted_baseline = (sum_25_3_7 * 0.7) + (sum_24_3_7 * 0.3)
                deviation = ((sum_pred_3_7 - weighted_baseline) / weighted_baseline * 100) if weighted_baseline > 0 else 0

                # 生成诊断文案
                if weighted_baseline == 0:
                    diag_alert = "🆕 **新品起盘/无历史数据基准**：请重点跟进当前流量和转化趋势进行备货验证。"
                elif deviation > 20:
                    diag_alert = f"⚠️ **【高估/滞销风险】**：当前预测激进，偏离加权同期基准 **+{deviation:.1f}%**！\n👉 *排雷提示*：请结合左侧定位确认，若为老品/清货款，哪来的自信爆单？请立刻复盘防范仓储滞压！"
                elif deviation < -20:
                    diag_alert = f"🚨 **【保守/断货风险】**：当前预测偏低，偏离加权同期基准 **{deviation:.1f}%**！\n👉 *排雷提示*：预测相较往年过于保守，请核实是遭遇强劲竞品打压，还是供应链备货受限？防范断货流失坑位。"
                else:
                    diag_alert = f"✅ **【备货健康】**：当前预测紧贴加权同期基准 (偏离度 **{deviation:.1f}%**)，整体规划较为合理。"

                # --- 渲染视图 (左图右诊) ---
                col_chart, col_diag = st.columns([3, 1])
                
                with col_chart:
                    fig = go.Figure()
                    # 历史均值线
                    fig.add_hline(y=hist_mean, line_dash="dash", line_color="gray", annotation_text=f"月均及格线: {int(hist_mean)}", annotation_position="top left")
                    # 折线
                    fig.add_trace(go.Scatter(x=months, y=y2024, mode='lines', name='2024 实际', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=months, y=y2025, mode='lines', name='2025 实际', line=dict(color='#2ca02c', width=2)))
                    fig.add_trace(go.Scatter(x=months, y=y2026_act, mode='lines+markers', name='2026 实际', line=dict(color='#ff7f0e', width=3)))
                    fig.add_trace(go.Scatter(x=months, y=y2026_pred, mode='lines+markers', name='2026 预测', line=dict(color='#ff7f0e', width=3, dash='dash')))

                    # 极值点标注
                    if max_val > 0:
                        fig.add_trace(go.Scatter(x=[max_month], y=[max_val], mode='markers+text', text=["🔴 销售峰值"], textposition="top center", marker=dict(color='red', size=10), showlegend=False, name="历史峰值"))
                    if min_val > 0:
                        fig.add_trace(go.Scatter(x=[min_month], y=[min_val], mode='markers+text', text=["🟢 销售低谷"], textposition="bottom center", marker=dict(color='green', size=10), showlegend=False, name="历史低谷"))

                    fig.update_layout(height=400, title=f"分析维度：{item}", margin=dict(t=40, b=10, l=10, r=10), hovermode='x unified', plot_bgcolor='white', legend=dict(orientation="h", y=1.05, x=0))
                    fig.update_xaxes(type='category', showgrid=True, gridcolor='WhiteSmoke')
                    fig.update_yaxes(showgrid=True, gridcolor='WhiteSmoke')
                    
                    st.plotly_chart(fig, use_container_width=True)

                with col_diag:
                    st.markdown("### 💡 AI 趋势诊断")
                    st.markdown(f"**🔥 综合核心旺季**：\n基于历史3个月滑动平滑，集中在 `{best_season}`。")
                    st.markdown(f"**❄️ 综合平淡淡季**：\n基于历史3个月滑动平滑，集中在 `{worst_season}`。")
                    st.markdown("---")
                    st.markdown("**🎯 3-7月预测排雷**：")
                    st.markdown(f"同期加权基准值 (25年x0.7+24年x0.3): `{int(weighted_baseline)}`")
                    st.markdown(f"未来4个月预测值: `{int(sum_pred_3_7)}`")
                    st.info(diag_alert)
                    
                st.markdown("---")

    except Exception as e:
        st.error(f"❌ 数据处理出错，请确认表格结构是否有变动。详细报错信息：{e}")
else:
    st.info("👈 **第一步：** 请在左侧侧边栏上传《销量统计》与《销量预测》表格以启用 V5.0 AI 诊断引擎。")
