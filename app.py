import streamlit as st
import pandas as pd
from prophet import Prophet
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import json

# Настройки страницы
st.set_page_config(page_title="Прогнозирование рекламы", layout="wide")
st.title("📈 Прогнозирование эффективности рекламных кампаний")

# --- 1. Загрузка данных ---
st.sidebar.header("Загрузка данных")
data_source = st.sidebar.radio(
    "Источник данных",
    ["CSV", "Яндекс.Директ", "CallTouch"]
)

df = None

if data_source == "CSV":
    uploaded_file = st.sidebar.file_uploader("Загрузите CSV файл", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.success("Данные успешно загружены!")

elif data_source == "Яндекс.Директ":
    st.sidebar.subheader("Настройки API Яндекс.Директ")
    yandex_token = st.sidebar.text_input("OAuth-токен Яндекс")
    client_id = st.sidebar.text_input("ID клиента")
    date_from = st.sidebar.date_input("Дата начала", datetime.now() - timedelta(days=30))
    date_to = st.sidebar.date_input("Дата окончания", datetime.now())

    if st.sidebar.button("Загрузить из Яндекс.Директ"):
        if yandex_token and client_id:
            url = "https://api.direct.yandex.com/json/v5/reports"
            headers = {
                "Authorization": f"Bearer {yandex_token}",
                "Client-Login": client_id,
                "Accept-Language": "ru"
            }
            body = {
                "params": {
                    "SelectionCriteria": {
                        "DateFrom": date_from.strftime("%Y-%m-%d"),
                        "DateTo": date_to.strftime("%Y-%m-%d")
                    },
                    "FieldNames": ["Date", "Clicks", "Cost", "Impressions", "Conversions"],
                    "ReportName": "Yandex Direct Report",
                    "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
                    "DateRangeType": "CUSTOM_DATE",
                    "Format": "TSV",
                    "IncludeVAT": "YES"
                }
            }
            response = requests.post(url, headers=headers, json=body)
            if response.status_code == 200:
                data = response.text.split("\n")
                df = pd.read_csv(pd.compat.StringIO("\n".join(data[1:-2])), sep="\t")
                df["Date"] = pd.to_datetime(df["Date"])
                st.success("Данные из Яндекс.Директ загружены!")
            else:
                st.error(f"Ошибка API: {response.text}")
        else:
            st.warning("Введите токен и ID клиента!")

elif data_source == "CallTouch":
    st.sidebar.subheader("Настройки API CallTouch")
    calltouch_api_key = st.sidebar.text_input("API-ключ CallTouch")
    calltouch_date_from = st.sidebar.date_input("Дата начала (CallTouch)", datetime.now() - timedelta(days=30))
    calltouch_date_to = st.sidebar.date_input("Дата окончания (CallTouch)", datetime.now())

    if st.sidebar.button("Загрузить из CallTouch"):
        if calltouch_api_key:
            url = f"https://api.calltouch.ru/calls-service/RestAPI/{calltouch_api_key}/calls-diary/calls"
            params = {
                "clientIds": "all",
                "dateFrom": calltouch_date_from.strftime("%Y-%m-%d"),
                "dateTo": calltouch_date_to.strftime("%Y-%m-%d"),
                "page": 1,
                "limit": 1000
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                calls_data = response.json()
                df = pd.DataFrame(calls_data["records"])
                df["callDate"] = pd.to_datetime(df["callDate"])
                st.success("Данные из CallTouch загружены!")
            else:
                st.error(f"Ошибка API CallTouch: {response.text}")
        else:
            st.warning("Введите API-ключ CallTouch!")

# --- 2. Просмотр данных ---
if df is not None:
    st.subheader("Данные для анализа")
    st.write(df.head())

    # --- 3. Выбор метрики для прогноза ---
    st.subheader("Настройка прогноза")
    metric_col = st.selectbox("Выберите метрику для прогноза", df.select_dtypes(include="number").columns)
    date_col = st.selectbox("Выберите столбец с датой", df.select_dtypes(include="datetime").columns)

    # Подготовка данных для Prophet
    prophet_df = df[[date_col, metric_col]].rename(columns={date_col: "ds", metric_col: "y"})

    # --- 4. Настройка модели ---
    st.sidebar.subheader("Параметры прогноза")
    forecast_period = st.sidebar.number_input("Горизонт прогноза (дни)", 1, 365, 30)
    seasonality_mode = st.sidebar.selectbox("Режим сезонности", ["additive", "multiplicative"])

    if st.button("Построить прогноз"):
        model = Prophet(seasonality_mode=seasonality_mode)
        model.fit(prophet_df)
        future = model.make_future_dataframe(periods=forecast_period)
        forecast = model.predict(future)

        # --- 5. Визуализация ---
        st.subheader("Результаты прогноза")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=forecast["ds"], y=forecast["yhat"], name="Прогноз"))
        fig.add_trace(go.Scatter(x=prophet_df["ds"], y=prophet_df["y"], name="Факт", mode="markers"))
        st.plotly_chart(fig, use_container_width=True)

        # Компоненты прогноза
        st.subheader("Компоненты прогноза")
        fig2 = model.plot_components(forecast)
        st.pyplot(fig2)
else:
    st.info("Загрузите данные для анализа (CSV, Яндекс.Директ или CallTouch).")
