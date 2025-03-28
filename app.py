import streamlit as st
import re
from collections import Counter
import pymorphy3
import pandas as pd
import hashlib
import base64
from io import StringIO
import chardet

# Настройки страницы
st.set_page_config(
    page_title="Маркетинг-инструменты",
    page_icon="🔧",
    layout="wide"
)

# ===== Инструмент 1: Генератор минус-слов =====
def prepare_morph_analyzer():
    return pymorphy3.MorphAnalyzer()

# ... (остальные функции генератора минус-слов остаются без изменений) ...

# ===== Инструмент 2: Хэширование телефонов =====
def hash_phone(phone):
    phone_str = str(phone).strip()
    if not phone_str:
        return ""
    digits = re.sub(r'\D', '', phone_str)
    if not digits:
        return ""
    return hashlib.sha256(digits.encode('utf-8')).hexdigest()

def get_table_download_link(df):
    """Генерирует ссылку для скачивания DataFrame"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="processed_data.csv">Скачать CSV</a>'

def read_uploaded_file(uploaded_file):
    """Чтение загруженного файла с обработкой ошибок"""
    try:
        if uploaded_file.name.endswith('.csv'):
            content = uploaded_file.getvalue()
            result = chardet.detect(content)
            encoding = result['encoding'] if result['confidence'] > 0.7 else 'utf-8'
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=encoding)
        else:
            # Пытаемся прочитать Excel с разными движками
            try:
                return pd.read_excel(uploaded_file, engine='openpyxl')
            except:
                try:
                    return pd.read_excel(uploaded_file, engine='xlrd')
                except:
                    st.error("Не удалось прочитать Excel-файл. Убедитесь, что установлены зависимости:")
                    st.code("pip install openpyxl xlrd")
                    return None
    except Exception as e:
        st.error(f"Ошибка чтения файла: {str(e)}")
        return None

# ===== Веб-интерфейс =====
st.title("🔧 Маркетинг-инструменты")
st.markdown("---")

tool = st.sidebar.radio(
    "Выберите инструмент",
    ["Генератор минус-слов", "Хэширование телефонов"],
    index=0
)

if tool == "Хэширование телефонов":
    st.header("📞 Хэширование номеров телефонов")
    
    uploaded_file = st.file_uploader(
        "Загрузите файл (Excel или CSV)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=False
    )
    
    if uploaded_file:
        df = read_uploaded_file(uploaded_file)
        
        if df is not None:
            st.success(f"Успешно загружено {len(df)} записей")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Предпросмотр данных")
                st.dataframe(df.head())
            
            with col2:
                st.subheader("Настройки обработки")
                phone_column = st.selectbox(
                    "Выберите столбец с телефонами",
                    df.columns,
                    index=0
                )
                
                new_column_name = st.text_input(
                    "Название для нового столбца с хэшами",
                    value="phone_hash"
                )
                
                if st.button("🔒 Хэшировать данные", type="primary"):
                    with st.spinner("Обработка..."):
                        try:
                            result_df = df.copy()
                            result_df[new_column_name] = result_df[phone_column].apply(hash_phone)
                            
                            st.success("Готово! Первые 5 строк:")
                            st.dataframe(result_df.head())
                            
                            st.markdown(get_table_download_link(result_df), unsafe_allow_html=True)
                        
                        except Exception as e:
                            st.error(f"Ошибка при обработке: {str(e)}")

# ... (остальная часть кода остается без изменений) ...
