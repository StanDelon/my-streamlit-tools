import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Настройки страницы
st.set_page_config(
    page_title="Яндекс.Директ Дашборд", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Заголовок
st.title("📊 Яндекс.Директ Дашборд (Demo)")
st.markdown("""
    *Это демо-версия дашборда с mock-данными. Для реального подключения к API Яндекс.Директ потребуется OAuth-токен.*
""")

# Генерация mock-данных
def generate_mock_data(date_from, date_to):
    campaigns = [
        "Кампания_1_Реклама_сайта",
        "Кампания_2_Мобильное_приложение",
        "Кампания_3_Сезонная_распродажа",
        "Кампания_4_Брендирование",
        "Кампания_5_Ретаргетинг"
    ]
    
    days = (date_to - date_from).days + 1
    date_range = pd.date_range(date_from, periods=days)
    
    data = []
    for date in date_range:
        for campaign in campaigns:
            clicks = int(50 + abs(hash(f"{date}{campaign}")) % 150)
            impressions = clicks * (30 + hash(f"{date}{campaign}") % 20)
            cost = clicks * (20 + hash(f"{date}{campaign}") % 15)
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            
            data.append({
                "Date": date.date(),
                "Campaign": campaign,
                "Clicks": clicks,
                "Impressions": impressions,
                "Cost": cost,
                "CTR": round(ctr, 2),
                "CPC": round(cost / clicks, 2) if clicks > 0 else 0
            })
    
    return pd.DataFrame(data)

# Сайдбар с настройками
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Выбор дат
    date_from = st.date_input(
        "Дата начала", 
        datetime.now().replace(day=1),
        key="date_from"
    )
    date_to = st.date_input(
        "Дата окончания", 
        datetime.now(),
        key="date_to"
    )
    
    # Фильтр кампаний
    st.header("🔍 Фильтры")
    all_campaigns = st.checkbox("Все кампании", True)
    if not all_campaigns:
        selected_campaigns = st.multiselect(
            "Выберите кампании",
            options=[],
            default=[],
            disabled=True,
            help="В демо-режиме доступны все кампании"
        )
    
    st.markdown("---")
    st.markdown("""
    **Для реального подключения:**
    1. Получите OAuth-токен в Яндекс.Директ
    2. Укажите логин клиента
    3. Замените mock-данные на реальные API-запросы
    """)

# Генерация данных
df = generate_mock_data(date_from, date_to)

# Ключевые метрики
st.subheader("📈 Ключевые показатели")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric(
    label="Общие клики", 
    value=f"{df['Clicks'].sum():,}",
    delta=f"{df['Clicks'].sum()/len(df['Date'].unique()):.0f} в день"
)
kpi2.metric(
    label="Общие показы", 
    value=f"{df['Impressions'].sum():,}",
    delta=f"{df['Impressions'].sum()/len(df['Date'].unique()):,.0f} в день"
)
kpi3.metric(
    label="Общий бюджет", 
    value=f"{df['Cost'].sum():,.0f} ₽",
    delta=f"{df['Cost'].sum()/len(df['Date'].unique()):,.0f} ₽ в день"
)
kpi4.metric(
    label="Средний CTR", 
    value=f"{df['CTR'].mean():.2f}%",
    delta=f"{df['CTR'].mean() - df[df['Date'] < df['Date'].max()]['CTR'].mean():.2f}%"
)

# Визуализации
tab1, tab2, tab3, tab4 = st.tabs(["📊 Динамика", "🔄 CTR", "💰 Расходы", "📋 Данные"])

with tab1:
    fig = px.line(
        df.groupby('Date').agg({
            'Clicks': 'sum',
            'Impressions': 'sum',
            'Cost': 'sum'
        }).reset_index(),
        x='Date',
        y=['Clicks', 'Impressions'],
        title='Динамика кликов и показов',
        labels={'value': 'Количество', 'variable': 'Метрика'},
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        fig_ctr = px.line(
            df.groupby('Date')['CTR'].mean().reset_index(),
            x='Date',
            y='CTR',
            title='Средний CTR по дням',
            labels={'CTR': 'CTR (%)'},
            height=400
        )
        st.plotly_chart(fig_ctr, use_container_width=True)
    
    with col2:
        fig_ctr_campaign = px.bar(
            df.groupby('Campaign')['CTR'].mean().sort_values().reset_index(),
            x='CTR',
            y='Campaign',
            orientation='h',
            title='CTR по кампаниям (средний)',
            labels={'CTR': 'CTR (%)', 'Campaign': 'Кампания'},
            height=400
        )
        st.plotly_chart(fig_ctr_campaign, use_container_width=True)

with tab3:
    fig_cost = px.area(
        df.groupby(['Date', 'Campaign'])['Cost'].sum().reset_index(),
        x='Date',
        y='Cost',
        color='Campaign',
        title='Распределение расходов по кампаниям',
        labels={'Cost': 'Расходы (₽)'},
        height=500
    )
    st.plotly_chart(fig_cost, use_container_width=True)

with tab4:
    st.dataframe(
        df.sort_values(['Date', 'Campaign']),
        column_config={
            "Date": st.column_config.DateColumn("Дата"),
            "Cost": st.column_config.NumberColumn("Расходы", format="%.0f ₽"),
            "CTR": st.column_config.NumberColumn("CTR", format="%.2f%%"),
            "CPC": st.column_config.NumberColumn("CPC", format="%.2f ₽")
        },
        hide_index=True,
        use_container_width=True
    )

# Footer
st.markdown("---")
st.markdown("""
    **GitHub:** [yandex-direct-dashboard](https://github.com/yourusername/yandex-direct-dashboard)  
    *Данные сгенерированы автоматически для демонстрации*
""")
