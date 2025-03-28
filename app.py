import streamlit as st
import re
from collections import Counter
import pymorphy3
import pandas as pd
import hashlib
import os
import chardet

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
    phone_str = str(phone)
    return hashlib.sha256(phone_str.encode('utf-8')).hexdigest()

# ===== Веб-интерфейс =====
st.title("Мои инструменты 🔧")
tool = st.sidebar.selectbox("Выберите инструмент", ["Генератор минус-слов", "Хэширование телефонов"])

if tool == "Генератор минус-слов":
    st.header("Генератор минус-слов")
    phrases = st.text_area("Введите фразы (каждая с новой строки)", height=150)
    exclude = st.text_area("Введите исключения (через запятую, | или /регэксп/)", height=100)
    
    if st.button("Сгенерировать минус-слова"):
        if not phrases:
            st.error("Введите фразы для обработки!")
        else:
            morph = prepare_morph_analyzer()
            exclude_list = parse_exclude_input(exclude)
            exclude_patterns = get_exclusion_patterns(exclude_list, morph)
            phrases_list = [p.strip() for p in phrases.split('\n') if p.strip()]
            minus_words = process_phrases(phrases_list, exclude_patterns, morph)
            result = " ".join([f"-{word}" for word in minus_words])
            st.success("Результат:")
            st.code(result)
            st.info(f"Найдено {len(minus_words)} минус-слов.")

elif tool == "Хэширование телефонов":
    st.header("Хэширование номеров телефонов")
    uploaded_file = st.file_uploader("Загрузите файл (Excel/CSV)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            phone_column = st.selectbox("Выберите столбец с телефонами", df.columns)
            
            if st.button("Хэшировать"):
                df[phone_column] = df[phone_column].apply(hash_phone)
                st.success("Готово! Первые 5 строк:")
                st.write(df.head())
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Скачать CSV",
                    data=csv,
                    file_name="hashed_phones.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"Ошибка: {e}")
