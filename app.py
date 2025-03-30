import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import base64

# --- Настройки страницы ---
st.set_page_config(page_title="Прогнозирование рекламы", layout="wide")
st.title("📈 Прогнозирование эффективности рекламных кампаний")

# --- 1. Шаблон CSV для скачивания ---
def create_download_link(filename):
    with open(filename, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Скачать шаблон CSV</a>'
    return href

st.sidebar.markdown(create_download_link("template.csv"), unsafe_allow_html=True)

# --- 2. Загрузка данных ---
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

elif data_source == "CallTouch":
    st.sidebar.subheader("Настройки API CallTouch")
    calltouch_api_key = st.sidebar.text_input("API-ключ CallTouch")
    date_from = st.sidebar.date_input("Дата начала", datetime.now() - timedelta(days=30))
    date_to = st.sidebar.date_input("Дата окончания", datetime.now())

    if st.sidebar.button("Загрузить из CallTouch"):
        if calltouch_api_key:
            url = f"https://api.calltouch.ru/calls-service/RestAPI/{calltouch_api_key}/calls-diary/calls"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json"
            }
            params = {
                "clientIds": "all",
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d"),
                "page": 1,
                "limit": 1000
            }
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    calls_data = response.json()
                    df = pd.DataFrame(calls_data["records"])
                    st.success("Данные из CallTouch загружены!")
                else:
                    st.error(f"Ошибка API CallTouch (код {response.status_code}): {response.text}")
            except Exception as e:
                st.error(f"Ошибка подключения: {str(e)}")
        else:
            st.warning("Введите API-ключ CallTouch!")

# ... (остальной код из предыдущей версии)
