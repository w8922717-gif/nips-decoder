import pandas as pd
import re
import streamlit as st
from streamlit_folium import st_folium
import folium
from mgrs import MGRS

st.set_page_config(page_title="Декодер военных координат NIPS", layout="wide", page_icon="🌐")

st.title("🌐 Декодер координат СУБД NIPS (IBM FFS) в WGS84")
st.markdown("Преобразование усеченных военных координат времен войны во Вьетнаме в географическую широту/долготу с визуализацией на карте.")

st.sidebar.header("⚙️ Настройки ГИС и региона")
utm_zone = st.sidebar.text_input("Зона UTM (GZD)", value="48Q", help="Например, 48Q для Северного/Центрального Вьетнама")
mgrs_square = st.sidebar.text_input("100-км квадрат MGRS", value="XE", help="Например, XE для района Донгхой / Тонкинский залив")

st.sidebar.markdown("---")
st.sidebar.markdown("**Справка по формату:** Программа автоматически очищает маркеры `E`, выравнивает координатные оси и делит строки на блоки.")

def parse_nips_string(raw_string):
    cleaned = raw_string.replace("E", "").strip()
    if len(cleaned) == 21:
        return [cleaned[:11], "0" + cleaned[11:]]
    elif len(cleaned) == 22:
        return [cleaned[:11], cleaned[11:]]
    else:
        tokens = re.findall(r"\d{10,11}", cleaned)
        return [t if len(t) == 11 else "0" + t for t in tokens]

def nips_to_wgs84(nips_token, zone, square):
    try:
        easting_raw = nips_token[:5]
        northing_raw = nips_token[6:11].ljust(5, '0')
        mgrs_string = f"{zone}{square}{easting_raw}{northing_raw}"
        m = MGRS()
        lat, lon = m.toWgs(mgrs_string.encode('utf-8'))
        return {"Токен NIPS": nips_token, "MGRS": mgrs_string, "Широта (Lat)": round(lat, 5), "Долгота (Lon)": round(lon, 5), "Статус": "Успешно"}
    except Exception as e:
        return {"Токен NIPS": nips_token, "MGRS": "Ошибка", "Широта (Lat)": None, "Долгота (Lon)": None, "Статус": f"Ошибка: {str(e)}"}

input_type = st.radio("Выберите способ ввода данных:", ('Вставить текст', 'Загрузить файл (.txt)'))

raw_data = ""
if input_type == 'Вставить текст':
    raw_data = st.text_area("Вставьте строки с логами NIPS сюда:", value="01075010670E1075210658E\n01073210663E1075310660E", height=150)
else:
    uploaded_file = st.file_uploader("Выберите текстовый файл с логами", type=["txt", "dat", "log"])
    if uploaded_file is not None:
        raw_data = uploaded_file.read().decode("utf-8")

if raw_data:
    lines = raw_data.splitlines()
    processed_records = []
    for line_idx, line in enumerate(lines, 1):
        if not line.strip(): continue
        tokens = parse_nips_string(line)
        for token in tokens:
            geo_info = nips_to_wgs84(token, utm_zone, mgrs_square)
            geo_info["Строка источника"] = line_idx
            processed_records.append(geo_info)
            
    df = pd.DataFrame(processed_records)
    df_valid = df[df["Широта (Lat)"].notna()].copy()
    col1, col2 = st.columns()
    
    with col1:
        st.subheader("📊 Результаты расшифровки")
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Скачать результат в CSV (для Excel/QGIS)", data=csv_data, file_name="nips_decoded_coordinates.csv", mime="text/csv")
        
    with col2:
        st.subheader("🗺️ Интерактивная ГИС-карта")
        if not df_valid.empty:
            center_lat = df_valid.iloc["Широта (Lat)"]
            center_lon = df_valid.iloc["Долгота (Lon)"]
            m = folium.Map(location=[center_lat, center_lon], zoom_start=11, control_scale=True)
            folium.TileLayer(tiles='https://google.com{x}&y={y}&z={z}', attr='Google Satellite Hybrid', name='Спутник (Google)', overlay=False, control=True).add_to(m)
            folium.LayerControl().add_to(m)
            track_points = []
            for idx, row in df_valid.iterrows():
                pt = [row["Широта (Lat)"], row["Долгота (Lon)"]]
                track_points.append(pt)
                popup_text = f"<b>Точка №{idx+1}</b><br>Строка: {row['Строка источника']}<br>NIPS: {row['Токен NIPS']}<br>Широта: {row['Широта (Lat)']}<br>Долгота: {row['Долгота (Lon)']}"
                folium.Marker(location=pt, popup=folium.Popup(popup_text, max_width=300), icon=folium.Icon(color="red" if idx==0 else "blue", icon="info-sign")).add_to(m)
            if len(track_points) > 1:
                folium.PolyLine(locations=track_points, color="darkred", weight=3, opacity=0.8).add_to(m)
            st_folium(m, width="100%", height=500, returned_objects=[])
        else:
            st.warning("Нет валидных координат для отображения.")
else:
    st.info("Ожидание ввода данных.")
