import streamlit as st
import re
from collections import Counter
import pandas as pd
import hashlib
import base64
import io
import chardet
from io import BytesIO

# Настройки страницы
st.set_page_config(
    page_title="Маркетинг-инструменты",
    page_icon="🔧",
    layout="wide"
)

# ===== Защита паролем =====
def check_password():
    """Проверка пароля"""
    def password_entered():
        if st.session_state["password"] == "gusev2025":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "Пароль", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Пароль", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.error("Неверный пароль")
        return False
    else:
        return True

if not check_password():
    st.stop()  # Не показывать остальное, пока пароль не введен

# ===== Инструмент 1: Генератор минус-слов =====
def normalize_word(word, force_exact=False):
    """Упрощенная нормализация без pymorphy3"""
    word = word.lower().strip('!') if force_exact or word.startswith('!') else word.lower()
    # Базовая нормализация (можно доработать)
    if word.endswith(('ом', 'ем', 'ой', 'ей', 'ами', 'ями')):
        return word[:-2]
    if word.endswith(('ы', 'и', 'а', 'я', 'у', 'ю')):
        return word[:-1]
    return word

def parse_exclude_input(user_input):
    """Парсинг исключений"""
    if not user_input:
        return []
    if '\n' in user_input:
        return [line.strip() for line in user_input.split('\n') if line.strip()]
    if '|' in user_input:
        return [item.strip() for item in user_input.split('|') if item.strip()]
    return [item.strip() for item in user_input.split(',') if item.strip()]

def get_exclusion_patterns(exclude_list):
    """Создание паттернов для исключений"""
    patterns = []
    for item in exclude_list:
        item = item.strip()
        if not item:
            continue
        if item.startswith('/') and item.endswith('/'):
            patterns.append((item[1:-1], True))
            continue
            
        force_exact = item.startswith('!')
        if force_exact:
            item = item[1:]
            
        if '*' in item:
            pattern = r'\b' + re.escape(item).replace(r'\*', r'\w*') + r'\b'
            patterns.append((pattern, False))
        else:
            normalized = normalize_word(item, force_exact)
            pattern = r'\b' + re.escape(normalized) + r'\b'
            patterns.append((pattern, False))
    return patterns

def should_exclude(word, exclude_patterns):
    """Проверка на исключение"""
    word_lower = word.lower()
    for pattern, is_regex in exclude_patterns:
        try:
            if is_regex or '*' in pattern:
                if re.search(pattern, word_lower, re.IGNORECASE):
                    return True
            else:
                if re.fullmatch(pattern, word_lower, re.IGNORECASE):
                    return True
        except re.error:
            continue
    return False

def process_phrases(phrases, exclude_patterns, min_word_length=3):
    """Обработка фраз"""
    words_counter = Counter()
    for phrase in phrases:
        words = re.findall(r'\b\w+\b', phrase.lower())
        for word in words:
            if len(word) >= min_word_length and not should_exclude(word, exclude_patterns):
                normalized = normalize_word(word)
                words_counter[normalized] += 1
    return sorted(words_counter.keys(), key=lambda x: (-words_counter[x], x))

# ===== Инструмент 2: Хэширование телефонов =====
def hash_phone(phone):
    """Хэширование телефона"""
    digits = re.sub(r'\D', '', str(phone))
    return hashlib.sha256(digits.encode()).hexdigest() if digits else ""

def read_uploaded_file(uploaded_file):
    """Чтение файла с обработкой CSV и Excel"""
    try:
        if uploaded_file.name.endswith('.csv'):
            # Для CSV определяем кодировку
            content = uploaded_file.getvalue()
            result = chardet.detect(content)
            encoding = result['encoding'] if result['confidence'] > 0.7 else 'utf-8'
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=encoding)
        
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            # Для Excel предлагаем конвертировать в CSV
            st.warning("Для обработки Excel-файлов сохраните его как CSV в Excel")
            st.info("Как конвертировать: Файл → Сохранить как → CSV (разделители - запятые)")
            return None
            
    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
        return None

def get_table_download_link(df):
    """Генерация ссылки для скачивания"""
    csv = df.to_csv(index=False).encode('utf-8-sig')
    b64 = base64.b64encode(csv).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="result.csv">Скачать CSV</a>'

# ===== Интерфейс =====
st.title("🔒 Маркетинг-инструменты (авторизованный доступ)")
st.markdown("---")

tool = st.sidebar.selectbox(
    "Выберите инструмент",
    ["Генератор минус-слов", "Хэширование телефонов"]
)

if tool == "Генератор минус-слов":
    st.header("📉 Генератор минус-слов")
    
    col1, col2 = st.columns(2)
    with col1:
        phrases = st.text_area(
            "Введите фразы для анализа (каждая с новой строки)",
            height=200,
            help="Фразы, которые нужно отминусовать"
        )
    
    with col2:
        exclude = st.text_area(
            "Исключения (через запятую или |)",
            height=200,
            help="Пример: слово1, (вариант1|вариант2), !точное, маска*"
        )
    
    if st.button("Сгенерировать"):
        if phrases:
            exclude_list = parse_exclude_input(exclude)
            exclude_patterns = get_exclusion_patterns(exclude_list)
            phrases_list = [p.strip() for p in phrases.split('\n') if p.strip()]
            minus_words = process_phrases(phrases_list, exclude_patterns)
            
            st.success("Результат:")
            st.code(" ".join([f"-{word}" for word in minus_words]))
            st.info(f"Найдено {len(minus_words)} минус-слов")
        else:
            st.error("Введите фразы для анализа")

elif tool == "Хэширование телефонов":
    st.header("📞 Хэширование телефонов")
    
    uploaded_file = st.file_uploader(
        "Загрузите CSV файл",
        type=["csv"],
        help="Excel-файлы предварительно сохраните как CSV"
    )
    
    if uploaded_file:
        df = read_uploaded_file(uploaded_file)
        if df is not None:
            st.success(f"Загружено {len(df)} записей")
            
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(df.head())
            
            with col2:
                phone_col = st.selectbox("Выберите столбец с телефонами", df.columns)
                new_col = st.text_input("Название для столбца с хэшами", "phone_hash")
                
                if st.button("Хэшировать"):
                    df[new_col] = df[phone_col].apply(hash_phone)
                    st.success("Готово! Пример:")
                    st.dataframe(df.head())
                    st.markdown(get_table_download_link(df), unsafe_allow_html=True)

# Футер
st.markdown("---")
st.caption("Версия 2.0 | © 2024 | Доступ ограничен")
