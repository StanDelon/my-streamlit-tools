import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import json
from io import StringIO

# Настройки страницы
st.set_page_config(
    page_title="Яндекс.Директ Дашборд | primepark-lynx", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Конфигурация API
CLIENT_LOGIN = "primepark-lynx"
TOKEN = "y0__xDUjbv7BxjcvTYgyK3Q1BL49Fo8XkTMl71y6FccfvfIbzpRxw"
BASE_URL = "https://api.direct.yandex.com/json/v5/"

# Заголовки для запросов
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Client-Login": CLIENT_LOGIN,
    "Accept-Language": "ru",
    "Content-Type": "application/json"
}

# Функция для получения списка кампаний
def get_campaigns():
    body = {
        "method": "get",
        "params": {
            "SelectionCriteria": {},
            "FieldNames": ["Id", "Name", "Status", "Type", "StartDate", "EndDate"],
        }
    }
    
    response = requests.post(
        f"{BASE_URL}campaigns",
        headers=HEADERS,
        json=body
    )
    
    if response.status_code == 200:
        return response.json().get("result", {}).get("Campaigns", [])
    else:
        st.error(f"Ошибка при получении кампаний: {response.text}")
        return []

# Функция для получения статистики
def get_statistics(date_from, date_to, campaign_ids=None):
    selection_criteria = {
        "DateFrom": date_from.strftime("%Y-%m-%d"),
        "DateTo": date_to.strftime("%Y-%m-%d")
    }
    
    if campaign_ids:
        selection_criteria["CampaignIds"] = campaign_ids
    
    body = {
        "params": {
            "SelectionCriteria": selection_criteria,
            "FieldNames": ["Date", "CampaignId", "CampaignName", "Clicks", "Impressions", "Cost", "Ctr"],
            "ReportName": "Campaign Performance",
            "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
            "DateRangeType": "CUSTOM_DATE",
            "Format": "TSV",
            "IncludeVAT": "YES",
            "IncludeDiscount": "NO"
        }
    }
    
    response = requests.post(
        f"{BASE_URL}reports",
        headers=HEADERS,
        json=body
    )
    
    if response.status_code == 200:
        # Преобразуем TSV в DataFrame
        data = StringIO(response.text)
        df = pd.read_csv(data, sep='\t')
        return df
    else:
        st.error(f"Ошибка при получении статистики: {response.text}")
        return pd.DataFrame()

# Интерфейс приложения
st.title(f"📊 Яндекс.Директ Дашборд | {CLIENT_LOGIN}")

# Сайдбар с настройками
with st.sidebar:
    st.header("⚙️ Настройки отчёта")
    
    # Выбор дат
    default_end = datetime.now()
    default_start = default_end - timedelta(days=30)
    
    date_from = st.date_input(
        "Дата начала", 
        default_start,
        key="date_from"
    )
    date_to = st.date_input(
        "Дата окончания", 
        default_end,
        key="date_to"
    )
    
    # Фильтр по кампаниям
    st.header("🔍 Фильтры")
    try:
        campaigns = get_campaigns()
        campaign_options = {c["Name"]: c["Id"] for c in campaigns}
        
        selected_names = st.multiselect(
            "Выберите кампании",
            options=list(campaign_options.keys()),
            default=list(campaign_options.keys())[:3] if campaign_options else []
        )
        selected_ids = [campaign_options[name] for name in selected_names]
    except Exception as e:
        st.error(f"Ошибка при загрузке кампаний: {str(e)}")
        selected_ids = None

# Получение данных
try:
    with st.spinner("Загрузка данных из Яндекс.Директ..."):
        df = get_statistics(date_from, date_to, selected_ids if selected_ids else None)
        
        if df.empty:
            st.warning("Нет данных для отображения. Проверьте настройки фильтров.")
            st.stop()
        
        # Преобразование данных
        df["Date"] = pd.to_datetime(df["Date"])
        df["CTR"] = df["Ctr"] * 100
        df["CPC"] = df.apply(lambda x: x["Cost"] / x["Clicks"] if x["Clicks"] > 0 else 0, axis=1)
        df.rename(columns={
            "CampaignName": "Campaign",
            "Ctr": "CTR_raw"
        }, inplace=True)

    # Ключевые метрики
    st.subheader("📈 Ключевые показатели")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    total_clicks = df["Clicks"].sum()
    total_impressions = df["Impressions"].sum()
    total_cost = df["Cost"].sum()
    avg_ctr = (df["Clicks"].sum() / df["Impressions"].sum() * 100) if df["Impressions"].sum() > 0 else 0
    
    kpi1.metric(
        label="Общие клики", 
        value=f"{total_clicks:,}",
        delta=f"{total_clicks/len(df['Date'].unique()):.0f} в день"
    )
    kpi2.metric(
        label="Общие показы", 
        value=f"{total_impressions:,}",
        delta=f"{total_impressions/len(df['Date'].unique()):,.0f} в день"
    )
    kpi3.metric(
        label="Общий бюджет", 
        value=f"{total_cost:,.0f} ₽",
        delta=f"{total_cost/len(df['Date'].unique()):,.0f} ₽ в день"
    )
    kpi4.metric(
        label="Средний CTR", 
        value=f"{avg_ctr:.2f}%",
        delta=f"{avg_ctr - (df[df['Date'] < df['Date'].max()]['Clicks'].sum() / df[df['Date'] < df['Date'].max()]['Impressions'].sum() * 100 if df[df['Date'] < df['Date'].max()]['Impressions'].sum() > 0 else 0):.2f}%"
    )

    # Визуализации
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Динамика", "🔄 CTR", "💰 Расходы", "📋 Данные"])

    with tab1:
        fig = px.line(
            df.groupby('Date').agg({
                'Clicks': 'sum',
                'Impressions': 'sum'
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
                labels={'CTR': 'CTR (%)'},
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
            df.sort_values(['Date', 'Campaign'])[['Date', 'Campaign', 'Clicks', 'Impressions', 'Cost', 'CTR', 'CPC']],
            column_config={
                "Date": st.column_config.DateColumn("Дата"),
                "Cost": st.column_config.NumberColumn("Расходы", format="%.0f ₽"),
                "CTR": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                "CPC": st.column_config.NumberColumn("CPC", format="%.2f ₽")
            },
            hide_index=True,
            use_container_width=True
        )

except Exception as e:
    st.error(f"Произошла ошибка: {str(e)}")

# Footer
st.markdown("---")
st.markdown(f"""
    **Аккаунт:** {CLIENT_LOGIN}  
    **Последнее обновление:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
""")
