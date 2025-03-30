import streamlit as st
import pandas as pd
from prophet import Prophet
import plotly.graph_objects as go
from datetime import datetime
import base64

# Настройки страницы
st.set_page_config(page_title="Прогнозирование рекламы", layout="wide")
st.title("📈 Прогнозирование эффективности рекламных кампаний")

# Функция для создания шаблона CSV
def create_download_link():
    csv = '''date,clicks,cost,conversions
2023-01-01,100,5000,15
2023-01-02,120,5500,18
2023-01-03,130,6000,20'''
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="template.csv">Скачать шаблон CSV</a>'
    return href

# Сайдбар с настройками
st.sidebar.header("Настройки данных")
st.sidebar.markdown(create_download_link(), unsafe_allow_html=True)

# Загрузка файла
uploaded_file = st.sidebar.file_uploader("Загрузите CSV файл", type=["csv"])

df = None

if uploaded_file is not None:
    try:
        # Чтение файла
        df = pd.read_csv(uploaded_file)
        
        # Поиск колонки с датой
        date_cols = [col for col in df.columns if any(x in col.lower() for x in ['date', 'time', 'day', 'ds'])]
        
        if not date_cols:
            st.error("Не найдена колонка с датами. Убедитесь, что в файле есть колонка с датой (например, 'date')")
            st.stop()
        
        date_col = date_cols[0]
        try:
            df[date_col] = pd.to_datetime(df[date_col])
        except:
            st.error(f"Не удалось преобразовать колонку '{date_col}' в дату. Проверьте формат дат.")
            st.stop()
        
        # Поиск числовых колонок
        numeric_cols = []
        for col in df.columns:
            if col != date_col:
                try:
                    df[col] = pd.to_numeric(df[col])
                    numeric_cols.append(col)
                except:
                    continue
        
        if not numeric_cols:
            st.error("Не найдены числовые колонки для анализа. Убедитесь, что в файле есть числовые данные.")
            st.stop()
        
        st.success("Данные успешно загружены!")
        st.write("Первые 5 строк данных:", df.head())
        
        # Настройка прогноза
        st.subheader("Настройка прогноза")
        metric_col = st.selectbox("Выберите метрику для прогноза", numeric_cols)
        forecast_period = st.slider("Горизонт прогноза (дней)", 1, 365, 30)
        seasonality_mode = st.selectbox("Режим сезонности", ["additive", "multiplicative"])
        
        if st.button("Построить прогноз"):
            try:
                # Подготовка данных
                prophet_df = df[[date_col, metric_col]].copy()
                prophet_df.columns = ['ds', 'y']
                prophet_df = prophet_df.dropna()
                
                if len(prophet_df) < 10:
                    st.error("Недостаточно данных для анализа. Нужно как минимум 10 наблюдений.")
                    st.stop()
                
                # Моделирование
                model = Prophet(seasonality_mode=seasonality_mode)
                model.fit(prophet_df)
                future = model.make_future_dataframe(periods=forecast_period)
                forecast = model.predict(future)
                
                # Визуализация
                st.subheader("Результаты прогноза")
                
                # Создаем фигуру Plotly
                fig = go.Figure()
                
                # Добавляем прогноз (линия)
                fig.add_trace(go.Scatter(
                    x=forecast['ds'],
                    y=forecast['yhat'],
                    name='Прогноз',
                    line=dict(color='blue', width=2)
                )
                
                # Добавляем фактические значения (точки)
                fig.add_trace(go.Scatter(
                    x=prophet_df['ds'],
                    y=prophet_df['y'],
                    name='Факт',
                    mode='markers',
                    marker=dict(color='red', size=5)
                )
                
                # Настройки графика
                fig.update_layout(
                    title=f'Прогноз для метрики "{metric_col}"',
                    xaxis_title='Дата',
                    yaxis_title=metric_col,
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Компоненты прогноза
                st.subheader("Компоненты прогноза")
                fig_components = model.plot_components(forecast)
                st.pyplot(fig_components)
                
            except Exception as e:
                st.error(f"Ошибка при построении прогноза: {str(e)}")
    
    except Exception as e:
        st.error(f"Ошибка загрузки файла: {str(e)}")
else:
    st.info("Загрузите CSV файл для анализа (используйте шаблон выше)")
