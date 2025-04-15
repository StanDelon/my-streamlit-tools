import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
from io import StringIO
import os

# Настройки страницы
st.set_page_config(
    page_title="Яндекс.Директ Дашборд",
    layout="wide",
    page_icon="📊"
)

# Загрузка конфигурации
try:
    TOKEN = st.secrets["YANDEX_TOKEN"]
    LOGIN = st.secrets["CLIENT_LOGIN"]
except:
    st.error("Не удалось загрузить конфигурацию. Проверьте secrets.toml")
    st.stop()

# Константы API
API_URL = "https://api.direct.yandex.com/json/v5/"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Client-Login": LOGIN,
    "Accept-Language": "ru",
    "Content-Type": "application/json"
}

# Функции для работы с API
def get_campaigns():
    body = {
        "method": "get",
        "params": {
            "SelectionCriteria": {},
            "FieldNames": ["Id", "Name", "Status"]
        }
    }
    
    try:
        response = requests.post(
            f"{API_URL}campaigns",
            headers=HEADERS,
            json=body
        )
        if response.status_code == 200:
            return response.json().get("result", {}).get("Campaigns", [])
        else:
            st.error(f"API Error: {response.json()}")
            return []
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return []

def get_report(date_from, date_to, campaign_ids=None):
    selection = {
        "DateFrom": date_from.strftime("%Y-%m-%d"),
        "DateTo": date_to.strftime("%Y-%m-%d")
    }
    
    if campaign_ids:
        selection["CampaignIds"] = campaign_ids
    
    body = {
        "params": {
            "SelectionCriteria": selection,
            "FieldNames": ["Date", "CampaignId", "CampaignName", 
                         "Clicks", "Impressions", "Cost", "Ctr"],
            "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
            "DateRangeType": "CUSTOM_DATE",
            "Format": "TSV",
            "IncludeVAT": "YES"
        }
    }
    
    try:
        response = requests.post(
            f"{API_URL}reports",
            headers=HEADERS,
            json=body
        )
        
        if response.status_code == 200:
            return pd.read_csv(StringIO(response.text), sep="\t")
        else:
            st.error(f"Report error: {response.text}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Report generation failed: {str(e)}")
        return pd.DataFrame()

# Интерфейс приложения
def main():
    st.title("📊 Яндекс.Директ Аналитика")
    
    # Сайдбар с настройками
    with st.sidebar:
        st.header("Параметры отчета")
        
        # Выбор даты
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        date_from = st.date_input("Начальная дата", start_date)
        date_to = st.date_input("Конечная дата", end_date)
        
        # Выбор кампаний
        st.header("Фильтры")
        with st.spinner("Загрузка кампаний..."):
            campaigns = get_campaigns()
        
        campaign_options = {c["Name"]: c["Id"] for c in campaigns}
        selected_campaigns = st.multiselect(
            "Кампании",
            options=list(campaign_options.keys()),
            default=list(campaign_options.keys())[:3] if campaign_options else []
        )
        
        selected_ids = [campaign_options[name] for name in selected_campaigns]
    
    # Основная область
    with st.spinner("Формирование отчета..."):
        df = get_report(date_from, date_to, selected_ids if selected_ids else None)
        
        if df.empty:
            st.warning("Нет данных для отображения")
            return
        
        # Обработка данных
        df["Date"] = pd.to_datetime(df["Date"])
        df["CTR"] = df["Ctr"] * 100
        df["CPC"] = df["Cost"] / df["Clicks"].replace(0, 1)
        df = df.rename(columns={"CampaignName": "Campaign"})
    
    # Ключевые метрики
    st.header("Ключевые показатели")
    cols = st.columns(4)
    with cols[0]:
        st.metric("Клики", f"{df['Clicks'].sum():,}")
    with cols[1]:
        st.metric("Показы", f"{df['Impressions'].sum():,}")
    with cols[2]:
        st.metric("Расходы", f"{df['Cost'].sum():,.0f} ₽")
    with cols[3]:
        st.metric("CTR", f"{df['Clicks'].sum() / df['Impressions'].sum() * 100:.2f}%")
    
    # Визуализации
    st.header("Визуализация данных")
    tab1, tab2, tab3 = st.tabs(["Динамика", "Эффективность", "Данные"])
    
    with tab1:
        fig = px.line(
            df.groupby("Date").sum().reset_index(),
            x="Date",
            y=["Clicks", "Impressions"],
            title="Динамика показов и кликов"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                df.groupby("Campaign").mean().reset_index(),
                x="Campaign",
                y="CTR",
                title="CTR по кампаниям"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.scatter(
                df,
                x="Cost",
                y="Clicks",
                color="Campaign",
                size="Impressions",
                title="Эффективность кампаний"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.dataframe(
            df.sort_values("Date"),
            column_config={
                "Date": st.column_config.DateColumn("Дата"),
                "Cost": st.column_config.NumberColumn("Расходы", format="%.0f ₽"),
                "CTR": st.column_config.NumberColumn("CTR", format="%.2f%%")
            },
            hide_index=True,
            use_container_width=True
        )

if __name__ == "__main__":
    main()
