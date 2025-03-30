import streamlit as st
import pandas as pd
from prophet import Prophet
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import base64
import io

# Настройки страницы
st.set_page_config(page_title="Прогнозирование рекламы", layout="wide")
st.title("📈 Прогнозирование эффективности рекламных кампаний")

# --- 1. Шаблон CSV для скачивания ---
def create_download_link():
    template = """date,clicks,cost,conversions,impressions,ctr
2024-01-01,150,5000,20,1000,15.0
2024-01-02,180,6000,25,1200,15.0"""
    b64 = base64.b64encode(template.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="template.csv">Скачать шаблон CSV</a>'
    return href

st.sidebar.markdown(create_download_link(), unsafe_allow_html=True)

# --- 2. Загрузка данных ---
data_source = st.sidebar.radio(
    "Источник данных",
    ["CSV", "Яндекс.Директ", "CallTouch"]
)

df = None

if data_source == "CSV":
    uploaded_file = st.sidebar.file_uploader("Загрузите CSV файл", type=["csv"])
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            df['date'] = pd.to_datetime(df['date'])
            st.success("Данные успешно загружены!")
            st.write("Первые 5 строк данных:", df.head())
        except Exception as e:
            st.error(f"Ошибка загрузки файла: {str(e)}")

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
                    "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
                    "DateRangeType": "CUSTOM_DATE",
                    "Format": "TSV",
                    "IncludeVAT": "YES"
                }
            }
            response = requests.post(url, headers=headers, json=body)
            if response.status_code == 200:
                data = response.text.split("\n")
                df = pd.read_csv(io.StringIO("\n".join(data[1:-2])), sep="\t")
                df['Date'] = pd.to_datetime(df['Date'])
                st.success("Данные из Яндекс.Директ загружены!")
            else:
                st.error(f"Ошибка API: {response.text}")

# --- 3. Построение прогноза ---
if df is not None:
    st.subheader("Настройка прогноза")
    
    # Выбор метрики
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    if not numeric_cols:
        st.error("Нет числовых колонок для анализа!")
    else:
        metric_col = st.selectbox("Выберите метрику для прогноза", numeric_cols)
        date_col = st.selectbox("Выберите колонку с датой", df.select_dtypes(include=['datetime64']).columns.tolist())
        
        # Настройки прогноза
        forecast_period = st.slider("Горизонт прогноза (дни)", 1, 365, 30)
        seasonality_mode = st.selectbox("Режим сезонности", ["additive", "multiplicative"])
        
        if st.button("Построить прогноз"):
            try:
                # Подготовка данных
                prophet_df = df[[date_col, metric_col]].rename(columns={date_col: "ds", metric_col: "y"})
                prophet_df = prophet_df.dropna()
                
                # Обучение модели
                model = Prophet(seasonality_mode=seasonality_mode)
                model.fit(prophet_df)
                
                # Прогнозирование
                future = model.make_future_dataframe(periods=forecast_period)
                forecast = model.predict(future)
                
                # Визуализация
                st.subheader("Результаты прогноза")
                
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(
                    x=forecast['ds'],
                    y=forecast['yhat'],
                    name="Прогноз",
                    line=dict(color='royalblue', width=3)
                ))
                fig1.add_trace(go.Scatter(
                    x=prophet_df['ds'],
                    y=prophet_df['y'],
                    name="Факт",
                    mode='markers',
                    marker=dict(color='red')
                ))
                fig1.update_layout(
                    title=f"Прогноз для метрики '{metric_col}'",
                    xaxis_title="Дата",
                    yaxis_title=metric_col
                )
                st.plotly_chart(fig1, use_container_width=True)
                
                # Компоненты прогноза
                st.subheader("Компоненты прогноза")
                fig2 = model.plot_components(forecast)
                st.pyplot(fig2)
                
            except Exception as e:
                st.error(f"Ошибка при построении прогноза: {str(e)}")
else:
    st.info("Загрузите данные для анализа (CSV, Яндекс.Директ или CallTouch).")
