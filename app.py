import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from yandex_direct import Client  # Библиотека для работы с API Яндекс.Директ

# Настройки страницы
st.set_page_config(page_title="Яндекс.Директ Дашборд", layout="wide")

# Заголовок
st.title("📊 Дашборд Яндекс.Директ")

# Авторизация в API
with st.sidebar:
    st.header("Авторизация")
    token = st.text_input("Токен доступа", type="password")
    login = st.text_input("Логин клиента")
    client = Client(token, login)

# Функция для получения данных
def get_campaign_stats(date_from, date_to):
    # Здесь код для получения данных из API Яндекс.Директ
    # Пример структуры данных:
    data = {
        "Campaign": ["Кампания 1", "Кампания 2", "Кампания 3"],
        "Clicks": [150, 200, 180],
        "Impressions": [5000, 7000, 6500],
        "Cost": [4500, 6000, 5500],
        "CTR": [3.0, 2.85, 2.77],
        "CPC": [30.0, 30.0, 30.55]
    }
    return pd.DataFrame(data)

# Выбор периода
col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input("Дата начала", datetime.now().replace(day=1))
with col2:
    date_to = st.date_input("Дата окончания", datetime.now())

# Получение данных
if token and login:
    df = get_campaign_stats(date_from, date_to)
    
    # Показатели эффективности
    st.subheader("Ключевые показатели")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Общие клики", df["Clicks"].sum())
    kpi2.metric("Общие показы", df["Impressions"].sum())
    kpi3.metric("Общий бюджет", f"{df['Cost'].sum():,} ₽")
    kpi4.metric("Средний CTR", f"{df['CTR'].mean():.2f}%")
    
    # Визуализации
    tab1, tab2, tab3 = st.tabs(["Расходы", "CTR", "CPC"])
    
    with tab1:
        fig = px.bar(df, x="Campaign", y="Cost", title="Расходы по кампаниям")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        fig = px.line(df, x="Campaign", y="CTR", title="CTR по кампаниям")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        fig = px.scatter(df, x="Clicks", y="CPC", color="Campaign", 
                        title="CPC vs Клики")
        st.plotly_chart(fig, use_container_width=True)
    
    # Таблица с данными
    st.subheader("Детальные данные")
    st.dataframe(df)
else:
    st.warning("Введите токен и логин для доступа к данным")
