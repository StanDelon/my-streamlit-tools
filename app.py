import streamlit as st
import re
from collections import Counter, defaultdict
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

def normalize_word(word, morph, force_exact=False):
    if force_exact or word.startswith('!'):
        return word.lstrip('!').lower()
    parsed = morph.parse(word.lower())[0]
    return parsed.normal_form

def parse_exclude_input(user_input):
    if not user_input:
        return []
    
    # Обработка многострочного ввода
    if '\n' in user_input:
        lines = [line.strip() for line in user_input.split('\n') if line.strip()]
        return [item for line in lines for item in parse_exclude_input(line)]
    
    # Обработка вариантов в скобках (word1|word2)
    if '(' in user_input and ')' in user_input and '|' in user_input:
        parts = []
        remaining = user_input
        while '(' in remaining and ')' in remaining:
            before = remaining[:remaining.index('(')]
            variant_part = remaining[remaining.index('(')+1:remaining.index(')')]
            after = remaining[remaining.index(')')+1:]
            
            if before.strip():
                parts.extend(parse_exclude_input(before))
            parts.extend(v.strip() for v in variant_part.split('|') if v.strip())
            remaining = after
        if remaining.strip():
            parts.extend(parse_exclude_input(remaining))
        return parts
    
    # Обычный ввод через запятую или |
    delimiters = [',', '|'] if '|' in user_input else [',']
    for delim in delimiters:
        if delim in user_input:
            return [item.strip() for item in user_input.split(delim) if item.strip()]
    
    return [user_input.strip()] if user_input.strip() else []

def get_exclusion_patterns(exclude_list, morph):
    patterns = []
    for item in exclude_list:
        item = item.strip()
        if not item:
            continue
            
        # Обработка регулярных выражений
        if item.startswith('/') and item.endswith('/'):
            pattern = item[1:-1]
            patterns.append((pattern, True, True))
            continue
            
        # Обработка точного совпадения
        force_exact = item.startswith('!')
        if force_exact:
            item = item[1:]
            
        # Обработка масок *
        if '*' in item:
            escaped = re.escape(item)
            pattern = escaped.replace(r'\*', r'\w*')
            pattern = r'\b' + pattern + r'\b'
            patterns.append((pattern, False, True))
        else:
            # Нормализация слова/фразы
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
    
    # Сортируем по частоте, затем по алфавиту
    return [word for word, count in sorted(words_counter.items(), key=lambda x: (-x[1], x[0]))]

# ===== Инструмент 2: Группировка семантического ядра =====
def parse_semantic_core(text):
    """Parse semantic core text into a list of phrases"""
    phrases = [line.strip() for line in text.split('\n') if line.strip()]
    return phrases

def build_hierarchy(phrases):
    """Build a hierarchical structure from phrases"""
    hierarchy = defaultdict(lambda: defaultdict(list))
    
    for phrase in phrases:
        parts = phrase.split()
        if len(parts) > 0:
            first_word = parts[0]
            rest = ' '.join(parts[1:]) if len(parts) > 1 else ''
            
            if rest:
                hierarchy[first_word][rest].append(phrase)
            else:
                hierarchy[first_word]['__LEAVES__'].append(phrase)
    
    return hierarchy

def display_hierarchy(hierarchy, level=0, excluded_words=None):
    """Recursively display hierarchy with checkboxes"""
    if excluded_words is None:
        excluded_words = set()
    
    for group, subgroups in sorted(hierarchy.items()):
        # Check if any phrase in this group is already excluded
        group_excluded = any(phrase in excluded_words for phrase in subgroups.get('__LEAVES__', []))
        
        # Create a unique key for the checkbox
        checkbox_key = f"group_{level}_{group}"
        
        # Display group checkbox
        excluded = st.checkbox(group, value=group_excluded, key=checkbox_key)
        
        if excluded:
            # Add all phrases in this group to excluded words
            if '__LEAVES__' in subgroups:
                excluded_words.update(subgroups['__LEAVES__'])
            
            # Add all nested phrases to excluded words
            for subgroup, phrases in subgroups.items():
                if subgroup != '__LEAVES__':
                    excluded_words.update(phrases)
        else:
            # Remove from excluded words if unchecked
            if '__LEAVES__' in subgroups:
                excluded_words.difference_update(subgroups['__LEAVES__'])
            
            for subgroup, phrases in subgroups.items():
                if subgroup != '__LEAVES__':
                    excluded_words.difference_update(phrases)
            
            # Display subgroups if any
            if len(subgroups) > 1 or (len(subgroups) == 1 and '__LEAVES__' not in subgroups):
                with st.expander(f"Подгруппы для '{group}'"):
                    for subgroup, phrases in subgroups.items():
                        if subgroup == '__LEAVES__':
                            continue
                            
                        # Check if any phrase in this subgroup is excluded
                        subgroup_excluded = any(phrase in excluded_words for phrase in phrases)
                        
                        # Create unique key for subgroup checkbox
                        subgroup_key = f"subgroup_{level}_{group}_{subgroup}"
                        
                        # Display subgroup checkbox
                        sub_excluded = st.checkbox(
                            subgroup, 
                            value=subgroup_excluded,
                            key=subgroup_key
                        )
                        
                        if sub_excluded:
                            excluded_words.update(phrases)
                        else:
                            excluded_words.difference_update(phrases)
                        
                        # Display phrases in this subgroup
                        with st.expander(f"Фразы в '{subgroup}'"):
                            for phrase in phrases:
                                st.write(phrase)
    
    return excluded_words

def semantic_core_grouper():
    st.header("📊 Группировка семантического ядра")
    st.write("Загрузите семантическое ядро (каждая фраза на новой строке)")
    
    uploaded_file = st.file_uploader("Выберите файл с семантическим ядром", type=['txt'], key="semantic_core_uploader")
    if uploaded_file is not None:
        text = uploaded_file.read().decode('utf-8')
        phrases = parse_semantic_core(text)
        
        if phrases:
            st.success(f"Загружено {len(phrases)} фраз")
            
            # Initialize session state for excluded words
            if 'excluded_words' not in st.session_state:
                st.session_state.excluded_words = set()
            
            # Build hierarchy
            hierarchy = build_hierarchy(phrases)
            
            st.subheader("Группировка фраз")
            excluded_words = display_hierarchy(
                hierarchy, 
                excluded_words=st.session_state.excluded_words
            )
            
            # Update session state
            st.session_state.excluded_words = excluded_words
            
            # Display excluded words
            st.subheader("Исключенные фразы")
            if st.session_state.excluded_words:
                st.write("\n".join(sorted(st.session_state.excluded_words)))
                if st.button("Очистить исключенные", key="clear_excluded"):
                    st.session_state.excluded_words = set()
                    st.experimental_rerun()
            else:
                st.write("Нет исключенных фраз")
            
            # Display remaining phrases
            st.subheader("Оставшиеся фразы")
            all_phrases = set(phrases)
            remaining_phrases = all_phrases - st.session_state.excluded_words
            st.write("\n".join(sorted(remaining_phrases)))
        else:
            st.warning("Не найдено фраз в файле")

# ===== Инструмент 3: Хэширование телефонов =====
def hash_phone(phone):
    phone_str = str(phone).strip()
    if not phone_str:
        return ""
    # Нормализация номера (удаляем всё, кроме цифр)
    digits = re.sub(r'\D', '', phone_str)
    if not digits:
        return ""
    return hashlib.sha256(digits.encode('utf-8')).hexdigest()

def get_table_download_link(df):
    """Генерирует ссылку для скачивания DataFrame"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="processed_data.csv">Скачать CSV</a>'

# ===== Веб-интерфейс =====
st.title("🔧 Маркетинг-инструменты")
st.markdown("---")

# Добавляем инструмент в меню
tool_options = [
    "Генератор минус-слов",
    "Группировка семантического ядра",
    "Хэширование телефонов"
]

tool = st.sidebar.radio(
    "Выберите инструмент",
    tool_options,
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
            help="Вставьте список фраз, которые нужно проанализировать",
            key="phrases_input"
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
            - Точные совпадения: !онлайн""",
            key="exclude_input"
        )
    
    st.markdown("---")
    st.subheader("3. Настройки обработки")
    
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        min_length = st.slider(
            "Минимальная длина слова",
            min_value=1,
            max_value=10,
            value=3,
            help="Слова короче указанной длины будут игнорироваться",
            key="min_length_slider"
        )
    
    with col_set2:
        show_stats = st.checkbox(
            "Показать статистику по словам",
            value=True,
            help="Отображает частоту встречаемости слов",
            key="show_stats_checkbox"
        )
    
    if st.button("🚀 Сгенерировать минус-слова", type="primary", key="generate_minus_words"):
        if not phrases:
            st.error("Введите фразы для анализа!")
        else:
            with st.spinner("Обработка данных..."):
                try:
                    morph = prepare_morph_analyzer()
                    exclude_list = parse_exclude_input(exclude)
                    exclude_patterns = get_exclusion_patterns(exclude_list, morph)
                    phrases_list = [p.strip() for p in phrases.split('\n') if p.strip()]
                    
                    minus_words = process_phrases(phrases_list, exclude_patterns, morph, min_length)
                    result = " ".join([f"-{word}" for word in minus_words])
                    
                    st.success("✅ Готово!")
                    
                    # Показываем результат в двух вариантах
                    tab1, tab2 = st.tabs(["Текстовый формат", "Список для копирования"])
                    
                    with tab1:
                        st.text_area(
                            "Результат (текст)",
                            value=result,
                            height=100,
                            key="result_text"
                        )
                    
                    with tab2:
                        st.text_area(
                            "Результат (по одному на строку)",
                            value="\n".join([f"-{word}" for word in minus_words]),
                            height=200,
                            key="result_list"
                        )
                    
                    if show_stats:
                        st.markdown("---")
                        st.subheader("📊 Статистика по словам")
                        
                        # Создаем DataFrame для визуализации
                        words_count = Counter()
                        for phrase in phrases_list:
                            words = re.findall(r'\b\w+\b', phrase.lower())
                            for word in words:
                                if len(word) >= min_length:
                                    normalized = normalize_word(word, morph)
                                    if not should_exclude(normalized, exclude_patterns):
                                        words_count[normalized] += 1
                        
                        df_stats = pd.DataFrame.from_dict(words_count, orient='index', columns=['Частота'])
                        df_stats = df_stats.sort_values(by='Частота', ascending=False)
                        
                        st.dataframe(df_stats.head(50))
                        
                        # Гистограмма топ-20 слов
                        st.bar_chart(df_stats.head(20))
                
                except Exception as e:
                    st.error(f"Ошибка обработки: {str(e)}")

elif tool == "Группировка семантического ядра":
    semantic_core_grouper()

elif tool == "Хэширование телефонов":
    st.header("📞 Хэширование номеров телефонов")
    
    uploaded_file = st.file_uploader(
        "Загрузите файл (Excel или CSV)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=False,
        key="phone_hash_uploader"
    )
    
    if uploaded_file:
        try:
            # Определяем тип файла и загружаем данные
            if uploaded_file.name.endswith('.csv'):
                # Пытаемся определить кодировку для CSV
                content = uploaded_file.getvalue()
                result = chardet.detect(content)
                encoding = result['encoding'] if result['confidence'] > 0.7 else 'utf-8'
                
                # Читаем CSV с учетом кодировки
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding=encoding)
            else:
                df = pd.read_excel(uploaded_file)
            
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
                    index=0,
                    key="phone_column_select"
                )
                
                new_column_name = st.text_input(
                    "Название для нового столбца с хэшами",
                    value="phone_hash",
                    key="new_column_name_input"
                )
                
                if st.button("🔒 Хэшировать данные", type="primary", key="hash_phones_button"):
                    with st.spinner("Обработка..."):
                        try:
                            # Создаем копию исходных данных
                            result_df = df.copy()
                            
                            # Хэшируем телефоны
                            result_df[new_column_name] = result_df[phone_column].apply(hash_phone)
                            
                            st.success("Готово! Первые 5 строк:")
                            st.dataframe(result_df.head())
                            
                            # Кнопка скачивания
                            st.markdown(get_table_download_link(result_df), unsafe_allow_html=True)
                        
                        except Exception as e:
                            st.error(f"Ошибка при обработке: {str(e)}")
        
        except Exception as e:
            st.error(f"Ошибка при загрузке файла: {str(e)}")

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
