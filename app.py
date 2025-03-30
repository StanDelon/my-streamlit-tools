import streamlit as st
import pandas as pd
from prophet import Prophet
import plotly.graph_objects as go
from datetime import datetime
import io

# Настройки страницы
st.set_page_config(page_title="Прогнозирование рекламы", layout="wide")
st.title("📈 Прогнозирование эффективности рекламных кампаний")

# Функция для прогнозирования
def make_forecast(df, date_col, metric_col, periods):
    try:
        # Подготовка данных для Prophet
        prophet_df = df[[date_col, metric_col]].rename(columns={date_col: "ds", metric_col: "y"})
        
        # Создание и обучение модели
        model = Prophet()
        model.fit(prophet_df)
        
        # Создание будущих дат
        future = model.make_future_dataframe(periods=periods)
        
        # Прогнозирование
        forecast = model.predict(future)
        
        return model, forecast
    except Exception as e:
        st.error(f"Ошибка при построении прогноза: {str(e)}")
        return None, None

# Загрузка данных
data_source = st.sidebar.radio(
    "Источник данных",
    ["CSV", "Яндекс.Директ", "CallTouch"]
)

df = None

if data_source == "CSV":
    uploaded_file = st.file_uploader("Загрузите CSV файл", type=["csv"])
    if uploaded_file is not None:
        try:
            # Чтение CSV файла
            df = pd.read_csv(uploaded_file)
            
            # Автоматическое определение столбца с датой
            date_cols = [col for col in df.columns if 'date' in col.lower() or 'дата' in col.lower()]
            date_col = date_cols[0] if date_cols else df.columns[0]
            
            # Автоматическое определение числовых столбцов
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            
            st.success("Данные успешно загружены!")
            st.write("Предпросмотр данных:")
            st.dataframe(df.head())
            
            # Выбор параметров для прогноза
            st.subheader("Настройки прогноза")
            date_col = st.selectbox("Выберите столбец с датой", df.columns, index=df.columns.get_loc(date_col))
            metric_col = st.selectbox("Выберите метрику для прогноза", numeric_cols)
            periods = st.number_input("Количество периодов для прогноза", min_value=1, max_value=365, value=30)
            
            if st.button("Построить прогноз"):
                with st.spinner('Строим прогноз...'):
                    model, forecast = make_forecast(df, date_col, metric_col, periods)
                    
                    if model is not None:
                        # Отображение прогноза
                        st.subheader("Результаты прогноза")
                        
                        # График прогноза
                        fig1 = go.Figure()
                        fig1.add_trace(go.Scatter(
                            x=forecast['ds'],
                            y=forecast['yhat'],
                            name='Прогноз',
                            line=dict(color='blue')
                        ))
                        fig1.add_trace(go.Scatter(
                            x=df[date_col],
                            y=df[metric_col],
                            name='Фактические данные',
                            mode='markers',
                            marker=dict(color='red')
                        ))
                        fig1.update_layout(
                            title=f'Прогноз для метрики "{metric_col}"',
                            xaxis_title='Дата',
                            yaxis_title=metric_col
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                        
                        # Компоненты прогноза
                        st.subheader("Компоненты прогноза")
                        fig2 = model.plot_components(forecast)
                        st.pyplot(fig2)
                        
                        # Скачивание прогноза
                        csv = forecast.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Скачать прогноз в CSV",
                            data=csv,
                            file_name='forecast.csv',
                            mime='text/csv'
                        )
        except Exception as e:
            st.error(f"Ошибка при обработке файла: {str(e)}")

# ... (остальные методы загрузки Яндекс.Директ и CallTouch)
