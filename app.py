import streamlit as st
import re
from collections import Counter
import pymorphy3
import pandas as pd
import hashlib
import base64
import io
import chardet
from io import BytesIO

# Настройки страницы
st.set_page_config(
    page_title="Генератор минус-слов",
    page_icon="🔍",
    layout="wide"
)

# Инициализация морфологического анализатора
try:
    morph = pymorphy3.MorphAnalyzer()
except ImportError:
    st.error("Ошибка: Не установлен модуль pymorphy3. Установите его командой: pip install pymorphy3")
    st.stop()

# Список исключений для топонимов (можно расширить)
TOPONYMS = {
    'москв': 'москва',
    'питер': 'санкт-петербург',
    'спб': 'санкт-петербург',
    'казан': 'казань',
    'новосиб': 'новосибирск',
    'екатеринбург': 'екатеринбург',
    'нижн': 'нижний новгород',
    'ростов': 'ростов-на-дону'
}

# ===== Функции нормализации =====
def normalize_word(word, force_exact=False):
    """Приводит слово к нормальной форме с учетом исключений"""
    if force_exact or word.startswith('!'):
        return word.lstrip('!').lower()
    
    # Проверка на топонимы
    word_lower = word.lower()
    for short, full in TOPONYMS.items():
        if word_lower.startswith(short):
            return full
    
    # Морфологический анализ
    parsed = morph.parse(word_lower)[0]
    
    # Для существительных используем именительный падеж
    if 'NOUN' in parsed.tag:
        return parsed.inflect({'nomn'}).word if parsed.inflect({'nomn'}) else parsed.normal_form
    
    # Для остальных - нормальную форму
    return parsed.normal_form

def parse_exclude_input(user_input):
    """Парсит ввод исключений"""
    if not user_input:
        return []
    
    # Обработка многострочного ввода
    if '\n' in user_input:
        lines = [line.strip() for line in user_input.split('\n') if line.strip()]
        return [item for line in lines for item in parse_exclude_input(line)]
    
    # Обработка вариантов через | или запятые
    delimiters = ['|', ','] if '|' in user_input else [',']
    for delim in delimiters:
        if delim in user_input:
            return [item.strip() for item in user_input.split(delim) if item.strip()]
    
    return [user_input.strip()] if user_input.strip() else []

def get_exclusion_patterns(exclude_list):
    """Создает regex-паттерны для исключений"""
    patterns = []
    for item in exclude_list:
        item = item.strip()
        if not item:
            continue
            
        # Обработка точного совпадения
        force_exact = item.startswith('!')
        if force_exact:
            item = item[1:]
            
        # Нормализация слова/фразы
        if ' ' in item:
            # Для фраз нормализуем каждое слово
            words = item.split()
            normalized_words = [normalize_word(w, force_exact) for w in words]
            pattern = r'\b' + r'\s+'.join(normalized_words) + r'\b'
        else:
            # Для отдельных слов
            normalized = normalize_word(item, force_exact)
            pattern = r'\b' + re.escape(normalized) + r'\b'
        
        patterns.append(pattern)
    return patterns

def should_exclude(word, exclude_patterns):
    """Проверяет, нужно ли исключать слово"""
    for pattern in exclude_patterns:
        if re.search(pattern, word, re.IGNORECASE):
            return True
    return False

def process_phrases(phrases, exclude_patterns, min_word_length=3):
    """Обрабатывает фразы и извлекает минус-слова"""
    words_counter = Counter()
    
    for phrase in phrases:
        # Извлекаем слова, игнорируя цифры и короткие слова
        words = re.findall(r'\b[a-zA-Zа-яА-ЯёЁ]{3,}\b', phrase.lower())
        for word in words:
            normalized = normalize_word(word)
            if not should_exclude(normalized, exclude_patterns):
                words_counter[normalized] += 1
    
    # Сортируем по частоте и алфавиту
    return sorted(words_counter.keys(), key=lambda x: (-words_counter[x], x))

# ===== Streamlit интерфейс =====
st.title("🔍 Генератор минус-слов с правильной нормализацией")
st.markdown("---")

# Входные данные
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Введите фразы для анализа")
    phrases_input = st.text_area(
        "Каждая фраза с новой строки",
        height=200,
        help="Пример:\nкупить цветы в москве\nдоставка цветов в питер"
    )

with col2:
    st.subheader("2. Укажите исключения")
    exclude_input = st.text_area(
        "Формат: слово1, слово2, (вариант1|вариант2)",
        height=200,
        help="Пример:\nцветы, !точное, доставк*, (москв|питер)"
    )

# Настройки обработки
st.markdown("---")
st.subheader("3. Настройки обработки")

min_length = st.slider(
    "Минимальная длина слова",
    min_value=2,
    max_value=10,
    value=3,
    help="Слова короче указанной длины будут игнорироваться"
)

show_stats = st.checkbox(
    "Показать статистику по словам",
    value=True,
    help="Отображает частоту встречаемости слов"
)

# Обработка
if st.button("🚀 Сгенерировать минус-слова", type="primary"):
    if not phrases_input:
        st.error("Введите фразы для анализа!")
    else:
        with st.spinner("Обработка данных..."):
            try:
                # Подготовка данных
                phrases_list = [p.strip() for p in phrases_input.split('\n') if p.strip()]
                exclude_list = parse_exclude_input(exclude_input)
                exclude_patterns = get_exclusion_patterns(exclude_list)
                
                # Генерация минус-слов
                minus_words = process_phrases(phrases_list, exclude_patterns, min_length)
                
                # Вывод результатов
                st.success("✅ Готово!")
                
                # Вкладки с разными форматами вывода
                tab1, tab2 = st.tabs(["Текстовый формат", "Подробный отчет"])
                
                with tab1:
                    st.text_area(
                        "Минус-слова (для копирования)",
                        value=" ".join([f"-{word}" for word in minus_words]),
                        height=100
                    )
                
                with tab2:
                    # Подсчет частоты слов
                    words_freq = Counter()
                    for phrase in phrases_list:
                        words = re.findall(r'\b[a-zA-Zа-яА-ЯёЁ]{3,}\b', phrase.lower())
                        for word in words:
                            normalized = normalize_word(word)
                            if not should_exclude(normalized, exclude_patterns):
                                words_freq[normalized] += 1
                    
                    # Создаем DataFrame для отчета
                    df_report = pd.DataFrame.from_dict(words_freq, orient='index', columns=['Частота'])
                    df_report = df_report.sort_values(by='Частота', ascending=False)
                    
                    st.dataframe(df_report)
                    st.bar_chart(df_report.head(20))
                
                st.info(f"Всего сгенерировано {len(minus_words)} минус-слов")
            
            except Exception as e:
                st.error(f"Ошибка обработки: {str(e)}")

# Футер
st.markdown("---")
st.caption("Версия 3.0 | Генератор минус-слов с правильной нормализацией")
