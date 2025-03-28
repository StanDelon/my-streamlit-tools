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
    
    if '\n' in user_input:
        lines = [line.strip() for line in user_input.split('\n') if line.strip()]
        return [item for line in lines for item in parse_exclude_input(line)]
    
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
    
    return [word for word, count in sorted(words_counter.items(), key=lambda x: (-x[1], x[0]))]

# ===== Инструмент 2: Группировка семантического ядра =====
def parse_semantic_core(text):
    """Разбивает текст на список фраз"""
    return [line.strip() for line in text.split('\n') if line.strip()]

def build_hierarchy(phrases):
    """Строит иерархию фраз с учетом частоты вхождений"""
    hierarchy = defaultdict(lambda: {
        'count': 0,
        'phrases': [],
        'subgroups': defaultdict(lambda: {'count': 0, 'phrases': []})
    })
    
    for phrase in phrases:
        words = phrase.split()
        
        # Находим все возможные группы от длинных к коротким
        possible_groups = []
        for i in range(1, len(words)+1):
            group = ' '.join(words[:i])
            possible_groups.append((group, i))
        
        possible_groups.sort(key=lambda x: -x[1])
        
        # Добавляем фразу в самую длинную подходящую группу
        added = False
        for group, _ in possible_groups:
            if group in hierarchy:
                remaining = ' '.join(words[len(group.split()):]).strip()
                if remaining:
                    hierarchy[group]['subgroups'][remaining]['phrases'].append(phrase)
                    hierarchy[group]['subgroups'][remaining]['count'] += 1
                else:
                    hierarchy[group]['phrases'].append(phrase)
                    hierarchy[group]['count'] += 1
                added = True
                break
        
        if not added:
            hierarchy[phrase]['phrases'].append(phrase)
            hierarchy[phrase]['count'] += 1
    
    # Преобразуем defaultdict в обычные dict для стабильности
    def convert_to_regular_dict(d):
        if isinstance(d, defaultdict):
            d = dict(d)
            for k, v in d.items():
                d[k] = convert_to_regular_dict(v)
        elif isinstance(d, dict):
            for k, v in d.items():
                d[k] = convert_to_regular_dict(v)
        return d
    
    hierarchy = convert_to_regular_dict(hierarchy)
    
    # Сортируем по количеству вхождений
    sorted_hierarchy = {}
    for group in sorted(hierarchy.keys(), key=lambda x: -hierarchy[x]['count']):
        sorted_subgroups = {}
        for subgroup in sorted(hierarchy[group]['subgroups'].keys(), 
                             key=lambda x: -hierarchy[group]['subgroups'][x]['count']):
            sorted_subgroups[subgroup] = hierarchy[group]['subgroups'][subgroup]
        
        sorted_hierarchy[group] = {
            'count': hierarchy[group]['count'],
            'phrases': hierarchy[group]['phrases'],
            'subgroups': sorted_subgroups
        }
    
    return sorted_hierarchy

def display_hierarchy(hierarchy, excluded_phrases=None):
    """Отображает иерархию с чекбоксами без вложенных expanders"""
    if excluded_phrases is None:
        excluded_phrases = set()
    
    # Создаем контейнер для отображения
    container = st.container()
    
    for group, data in hierarchy.items():
        with container:
            # Отображаем группу
            col1, col2 = st.columns([1, 4])
            with col1:
                group_excluded = st.checkbox(
                    f"{group} ({data['count']})", 
                    value=all(phrase in excluded_phrases for phrase in data['phrases']),
                    key=f"group_{group}"
                )
            
            if group_excluded:
                excluded_phrases.update(data['phrases'])
            else:
                excluded_phrases.difference_update(data['phrases'])
            
            # Отображаем подгруппы
            if data['subgroups']:
                subgroup_container = st.container()
                with subgroup_container:
                    st.write("Подгруппы:")
                    for subgroup, sub_data in data['subgroups'].items():
                        sub_col1, sub_col2 = st.columns([1, 4])
                        with sub_col1:
                            sub_excluded = st.checkbox(
                                f"{subgroup} ({sub_data['count']})",
                                value=all(phrase in excluded_phrases for phrase in sub_data['phrases']),
                                key=f"subgroup_{group}_{subgroup}"
                            )
                        
                        if sub_excluded:
                            excluded_phrases.update(sub_data['phrases'])
                        else:
                            excluded_phrases.difference_update(sub_data['phrases'])
                        
                        # Отображаем фразы подгруппы
                        if sub_data['phrases']:
                            with st.expander(f"Показать фразы ({len(sub_data['phrases'])})"):
                                for phrase in sub_data['phrases']:
                                    st.write(phrase)
            
            # Отображаем фразы группы
            if data['phrases']:
                with st.expander(f"Фразы группы ({len(data['phrases'])})"):
                    for phrase in data['phrases']:
                        st.write(phrase)
    
    return excluded_phrases

def semantic_core_grouper():
    st.header("📊 Группировка семантического ядра")
    
    example_phrases = """
сборка душевой кабины villagio
сборка душевой кабины villagio 120 80 215
сборка душевой кабины villagio ks 6690m
сборка душевой кабины виладжио
сборка душевой кабины вилладжио
ремонт душевой кабины
ремонт душевой кабины villagio
установка душевой кабины
установка душевой кабины виладжио
"""
    
    st.subheader("1. Загрузите семантическое ядро")
    input_type = st.radio("Выберите источник данных", ["Пример данных", "Загрузить файл"], key="data_source")
    
    if input_type == "Пример данных":
        phrases = parse_semantic_core(example_phrases)
    else:
        uploaded_file = st.file_uploader("Выберите текстовый файл", type=['txt'], key="core_uploader")
        if uploaded_file:
            text = uploaded_file.read().decode('utf-8')
            phrases = parse_semantic_core(text)
        else:
            st.warning("Пожалуйста, загрузите файл")
            return
    
    if not phrases:
        st.error("Не найдено фраз для анализа!")
        return
    
    st.success(f"Загружено {len(phrases)} фраз")
    
    st.subheader("2. Группировка фраз")
    hierarchy = build_hierarchy(phrases)
    
   if 'excluded_phrases' not in st.session_state:
        st.session_state.excluded_phrases = set()
    
    # Создаем контейнер для иерархии
    hierarchy_container = st.container()
    with hierarchy_container:
        st.session_state.excluded_phrases = display_hierarchy(
            hierarchy,
            st.session_state.excluded_phrases
        )
    
    st.subheader("3. Управление исключениями")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Очистить все исключения", key="clear_exclusions"):
            st.session_state.excluded_phrases = set()
            st.experimental_rerun()
    
    with col2:
        if st.button("Исключить все фразы", key="exclude_all"):
            st.session_state.excluded_phrases = set(phrases)
            st.experimental_rerun()
    
    st.subheader("4. Результаты")
    
    tab1, tab2 = st.tabs(["Исключенные фразы", "Оставшиеся фразы"])
    
    with tab1:
        if st.session_state.excluded_phrases:
            st.write("\n".join(sorted(st.session_state.excluded_phrases)))
        else:
            st.info("Нет исключенных фраз")
    
    with tab2:
        remaining = set(phrases) - st.session_state.excluded_phrases
        if remaining:
            st.write("\n".join(sorted(remaining)))
        else:
            st.warning("Все фразы исключены")

# ===== Инструмент 3: Хэширование телефонов =====
def hash_phone(phone):
    phone_str = str(phone).strip()
    if not phone_str:
        return ""
    digits = re.sub(r'\D', '', phone_str)
    if not digits:
        return ""
    return hashlib.sha256(digits.encode('utf-8')).hexdigest()

def get_table_download_link(df):
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="processed_data.csv">Скачать CSV</a>'

# ===== Веб-интерфейс =====
st.title("🔧 Маркетинг-инструменты")
st.markdown("---")

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
            if uploaded_file.name.endswith('.csv'):
                content = uploaded_file.getvalue()
                result = chardet.detect(content)
                encoding = result['encoding'] if result['confidence'] > 0.7 else 'utf-8'
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
                            result_df = df.copy()
                            result_df[new_column_name] = result_df[phone_column].apply(hash_phone)
                            st.success("Готово! Первые 5 строк:")
                            st.dataframe(result_df.head())
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
