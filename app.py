import streamlit as st
import re
from collections import Counter
import pymorphy3
import pandas as pd
import hashlib
import base64
import io
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

def normalize_word(word, morph, force_exact=False):
    if force_exact or word.startswith('!'):
        return word.lstrip('!').lower()
    parsed = morph.parse(word.lower())[0]
    return parsed.normal_form

def parse_exclude_input(user_input):
    if '\n' in user_input:
        return [line.strip() for line in user_input.split('\n') if line.strip()]
    if '|' in user_input and '(' not in user_input and ')' not in user_input:
        return [item.strip() for item in user_input.split('|') if item.strip()]
    return [item.strip() for item in user_input.split(',') if item.strip()]

def get_exclusion_patterns(exclude_list, morph):
    patterns = []
    for item in exclude_list:
        item = item.strip()
        if not item:
            continue
        if item.startswith('/') and item.endswith('/'):
            pattern = item[1:-1]
            patterns.append((pattern, True, True))
            continue
        force_exact = item.startswith('!')
        if force_exact:
            item = item[1:]
        if '*' in item:
            escaped = re.escape(item)
            pattern = escaped.replace(r'\*', r'\w*')
            pattern = r'\b' + pattern + r'\b'
            patterns.append((pattern, False, True))
        else:
            words = re.findall(r'\w+', item.lower())
            normalized_words = [normalize_word(w, morph, force_exact) for w in words]
            pattern = r'\b' + r'\s+'.join(normalized_words) + r'\b'
            patterns.append((pattern, False, False))
    return patterns

def should_exclude(word, exclude_patterns):
    word_lower = word.lower()
    for pattern, is_regex, is_wildcard in exclude_patterns:
        try:
            if is_regex:
                if re.search(pattern, word_lower, re.IGNORECASE):
                    return True
            elif is_wildcard:
                if re.search(pattern, word_lower, re.IGNORECASE):
                    return True
            else:
                if re.fullmatch(pattern, word_lower, re.IGNORECASE):
                    return True
        except re.error:
            continue
    return False

def process_phrases(phrases, exclude_patterns, morph, min_word_length=3):
    words_counter = Counter()
    for phrase in phrases:
        words = re.findall(r'\b\w+\b', phrase.lower())
        for word in words:
            if len(word) >= min_word_length and not should_exclude(word, exclude_patterns):
                normalized = normalize_word(word, morph)
                words_counter[normalized] += 1
    sorted_words = sorted(words_counter.items(), key=lambda x: (-x[1], x[0]))
    return [word for word, count in sorted_words]

# ===== Инструмент 2: Хэширование телефонов =====
def hash_phone(phone):
    phone_str = str(phone).strip()
    if not phone_str:
        return ""
    digits = re.sub(r'\D', '', phone_str)
    if not digits:
        return ""
    return hashlib.sha256(digits.encode('utf-8')).hexdigest()

def read_uploaded_file(uploaded_file):
    """Чтение файла с автоматической конвертацией Excel в CSV"""
    try:
        if uploaded_file.name.endswith('.csv'):
            content = uploaded_file.getvalue()
            result = chardet.detect(content)
            encoding = result['encoding'] if result['confidence'] > 0.7 else 'utf-8'
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=encoding), None
        
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            # Читаем Excel и создаем CSV в памяти
            df = pd.read_excel(uploaded_file)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()
            return df, csv_content
        
        else:
            st.error("Неподдерживаемый формат файла")
            return None, None
            
    except Exception as e:
        st.error(f"Ошибка обработки файла: {str(e)}")
        return None, None

def get_table_download_link(df, format='csv'):
    """Генерирует ссылки для скачивания"""
    if format == 'csv':
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
        return f'<a href="data:file/csv;base64,{b64}" download="processed_data.csv">Скачать CSV</a>'
    else:
        excel = io.BytesIO()
        with pd.ExcelWriter(excel, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        excel.seek(0)
        b64 = base64.b64encode(excel.read()).decode()
        return f'<a href="data:application/vnd.ms-excel;base64,{b64}" download="processed_data.xlsx">Скачать Excel</a>'

# ===== Веб-интерфейс =====
st.title("🔧 Маркетинг-инструменты")
st.markdown("---")

tool = st.sidebar.radio(
    "Выберите инструмент",
    ["Генератор минус-слов", "Хэширование телефонов"],
    index=0
)

if tool == "Генератор минус-слов":
    st.header("📉 Генератор минус-слов для рекламы")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Введите фразы для анализа")
        phrases = st.text_area(
            "Каждая фраза с новой строки",
            height=200,
            help="Вставьте список фраз, которые нужно проанализировать"
        )
        
    with col2:
        st.subheader("2. Укажите исключения")
        exclude = st.text_area(
            "Формат: слово1, слово2, (вариант1|вариант2), /регэксп/",
            height=200,
            help="""Можно использовать:
            - Запятые: слово1, слово2
            - Варианты: (вилладжио|villagio)
            - Маски: ремонт*
            - Регулярки: /цена|стоимость/
            - Точные совпадения: !онлайн"""
        )
    
    if st.button("🚀 Сгенерировать минус-слова", type="primary"):
        if not phrases:
            st.error("Введите фразы для анализа!")
        else:
            with st.spinner("Обработка данных..."):
                try:
                    morph = prepare_morph_analyzer()
                    exclude_list = parse_exclude_input(exclude)
                    exclude_patterns = get_exclusion_patterns(exclude_list, morph)
                    phrases_list = [p.strip() for p in phrases.split('\n') if p.strip()]
                    
                    minus_words = process_phrases(phrases_list, exclude_patterns, morph)
                    result = " ".join([f"-{word}" for word in minus_words])
                    
                    st.success("✅ Готово!")
                    st.text_area("Результат", value=result, height=100)
                    st.info(f"Найдено {len(minus_words)} минус-слов")
                
                except Exception as e:
                    st.error(f"Ошибка обработки: {str(e)}")

elif tool == "Хэширование телефонов":
    st.header("📞 Хэширование номеров телефонов")
    
    uploaded_file = st.file_uploader(
        "Загрузите файл (Excel или CSV)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=False
    )
    
    if uploaded_file:
        df, converted_csv = read_uploaded_file(uploaded_file)
        
        if df is not None:
            st.success(f"Успешно загружено {len(df)} записей")
            
            if uploaded_file.name.endswith(('.xlsx', '.xls')) and converted_csv:
                st.download_button(
                    label="Скачать конвертированный CSV",
                    data=converted_csv,
                    file_name="converted.csv",
                    mime="text/csv"
                )
            
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
                            
                            st.markdown(get_table_download_link(result_df, 'csv'), unsafe_allow_html=True)
                            st.markdown(get_table_download_link(result_df, 'excel'), unsafe_allow_html=True)
                        
                        except Exception as e:
                            st.error(f"Ошибка при обработке: {str(e)}")

# Футер
st.markdown("---")
st.markdown("""
<style>
.footer {
    font-size: small;
    color: gray;
    text-align: center;
}
</style>
<div class="footer">
    Маркетинг-инструменты | 2023
</div>
""", unsafe_allow_html=True)
