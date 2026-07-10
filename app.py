import streamlit as st
import yfinance as yf
import pandas as pd
import os
import csv
from datetime import datetime

# --- 1. SAYFA VE ARAYÜZ AYARLARI ---
st.set_page_config(page_title="Portföy Rebalancing Pro", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# --- ESTETİK VE RENKLENDİRME ---
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    [data-testid="stSidebar"] {
        background-color: #B4E1EB !important;
    }
    [data-testid="stAppViewContainer"] > .main {
        background-color: #F4F9F9 !important; 
    }
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 2px solid #95BDD7; 
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0px 4px 10px rgba(120, 164, 203, 0.15);
        transition: transform 0.2s ease-in-out, border-color 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        border-color: #78A4CB; 
    }
    button[kind="primary"] {
        background-color: #78A4CB !important; 
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        transition: all 0.3s ease;
    }
    button[kind="primary"]:hover {
        background-color: #95BDD7 !important; 
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Portföy Yeniden Dengeleme Yönetimi")
st.markdown("Belirlediğiniz stratejiye göre algoritmik rebalancing işlemlerinizi buradan yönetin.")
st.divider()

# --- VARLIK SÖZLÜĞÜ ---
VARLIK_SOZLUGU = {
    "Altın": "GC=F", "Gümüş": "SI=F", "Petrol": "CL=F", "Ham Petrol": "CL=F",
    "Doğalgaz": "NG=F", "Buğday": "ZW=F", "Mısır": "ZC=F",
    "Bakır": "HG=F", "Kahve": "KC=F", "Platin": "PL=F",
    "Pamuk": "CT=F", "Bitcoin (BTC)": "BTC-USD", "Ethereum (ETH)": "ETH-USD"
}

# --- VERİ DOSYASI YOLU ---
DOSYA_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rebalancing_gecmisi.csv")

# --- 2. OTURUM HAFIZASI ---
if "ana_sermaye" not in st.session_state:
    st.session_state.ana_sermaye = 0.0
if "nakit" not in st.session_state:
    st.session_state.nakit = 0.0
if "referans_fiyat" not in st.session_state:
    st.session_state.referans_fiyat = 0.0
if "guncel_fiyat" not in st.session_state:
    st.session_state.guncel_fiyat = 0.0
if "sistem_aktif" not in st.session_state:
    st.session_state.sistem_aktif = False
if "hedef_oran" not in st.session_state:
    st.session_state.hedef_oran = 50.0
if "emtia_miktari" not in st.session_state:
    st.session_state.emtia_miktari = 0.0


# --- 3. YARDIMCI FONKSİYONLAR ---
def turkce_format(sayi):
    if sayi is None:
        return "0,00"
    return f"{float(sayi):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_commodity_price(symbol):
    try:
        ticker_data = yf.Ticker(symbol)
        hist_live = ticker_data.history(period="1d", interval="1m")
        if not hist_live.empty:
            return round(hist_live['Close'].iloc[-1], 2)
        hist_daily = ticker_data.history(period="5d")
        if not hist_daily.empty:
            return round(hist_daily['Close'].iloc[-1], 2)
        return None
    except:
        return None


def islem_kaydet_csv(log_kaydi, dosya_adi=DOSYA_YOLU):
    dosya_var_mi = os.path.isfile(dosya_adi)
    with open(dosya_adi, mode='a', newline='', encoding='utf-8') as dosya:
        alanlar = ["Tarih", "Varlık", "Eski Fiyat", "Yeni Fiyat", "İşlem Türü", "İşlem Miktarı", "İşlem Tutarı",
                   "Yeni Sermaye", "Hedef Oran", "Yeni Emtia Miktarı"]
        writer = csv.DictWriter(dosya, fieldnames=alanlar)
        if not dosya_var_mi:
            writer.writeheader()
        writer.writerow(log_kaydi)


# --- 4. SOL MENÜ (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Parametreler")

    secim_turu = st.radio("Varlık Seçim Yöntemi", ["Listeden Seç", "Sembol Gir (Örn: AAPL)"])
    if secim_turu == "Listeden Seç":
        secilen_varlik = st.selectbox("🎯 İşlem Yapılacak Varlık", list(VARLIK_SOZLUGU.keys()))
        sembol = VARLIK_SOZLUGU[secilen_varlik]
    else:
        ozel_sembol = st.text_input("🔍 Sembol Girin:").strip().upper()
        secilen_varlik = ozel_sembol
        sembol = ozel_sembol

    st.divider()
    baslangic_sermayesi = st.number_input("💰 Ana Sermaye ($)", min_value=1.0, value=10000.0, step=100.0)
    baslangic_orani = st.number_input("⚖️ Başlangıç Emtia Oranı (%)", min_value=1.0, max_value=100.0, value=50.0,
                                      step=1.0)
    adim_araligi = st.number_input("📈 Adım Aralığı (%)", min_value=0.1, value=5.0, step=0.5)

    st.markdown("### ⚖️ Manuel Tolerans Bantları")
    ust_sinir = st.number_input("Üst Sınır (Kâr Realizasyon Marjı) %", min_value=1.0, value=80.0, step=1.0,
                                help="Bu seviyeye ulaşılırsa oran otomatik düşürülür.")
    alt_sinir = st.number_input("Alt Sınır (Maliyet Düşürme Marjı) %", min_value=1.0, value=40.0, step=1.0,
                                help="Bu seviyeye inilirse oran otomatik artırılır.")
    oran_degisim_ust = st.number_input("Üst Sınır İçin Dinamik Geçiş Oranı (%)", min_value=1.0, value=5.0, step=1.0)
    oran_degisim_alt = st.number_input("Alt Sınır İçin Dinamik Geçiş Oranı (%)", min_value=1.0, value=5.0, step=1.0)
    st.divider()

    ilk_fiyat_manuel = st.number_input("İlk Fiyat ($)", min_value=0.0, value=0.0, step=10.0,
                                       help="0 bırakırsanız otomatik çekilir.")

    if st.button("🚀 Sistemi Başlat", use_container_width=True, type="primary"):
        if not sembol:
            st.error("Lütfen geçerli bir sembol girin!")
        else:
            fiyat = ilk_fiyat_manuel if ilk_fiyat_manuel > 0 else get_commodity_price(sembol)
            if fiyat:
                st.session_state.ana_sermaye = baslangic_sermayesi
                st.session_state.referans_fiyat = fiyat
                st.session_state.guncel_fiyat = fiyat
                st.session_state.hedef_oran = baslangic_orani
                emtia_degeri = (baslangic_orani * baslangic_sermayesi) / 100
                st.session_state.emtia_miktari = emtia_degeri / fiyat
                st.session_state.nakit = baslangic_sermayesi - emtia_degeri
                st.session_state.sistem_aktif = True
                st.rerun()
            else:
                st.error("Fiyat çekilemedi.")

# --- 5. ANA EKRAN ---
if st.session_state.sistem_aktif:
    current_commodity_value = st.session_state.emtia_miktari * st.session_state.guncel_fiyat
    current_total_capital = st.session_state.nakit + current_commodity_value
    current_commodity_ratio = (
                                          current_commodity_value / current_total_capital) * 100 if current_total_capital > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Toplam Sermaye", f"${turkce_format(current_total_capital)}")
    col2.metric(f"Aktif Hedef Oran", f"%{turkce_format(st.session_state.hedef_oran)}")
    col3.metric("Anlık Varlık Oranı", f"%{turkce_format(current_commodity_ratio)}")
    col4.metric("Referans Fiyat", f"${turkce_format(st.session_state.referans_fiyat)}")

    degisim_yuzdesi = ((
                                   st.session_state.guncel_fiyat - st.session_state.referans_fiyat) / st.session_state.referans_fiyat) * 100
    col5.metric("Güncel Fiyat", f"${turkce_format(st.session_state.guncel_fiyat)}",
                f"{turkce_format(degisim_yuzdesi)}%")

    st.markdown("<br>", unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🔄 Aksiyon Paneli", "📂 Raporlama", "🛠️ Veri Yönetimi"])

    with tab1:
        st.subheader(f"⚡ {secilen_varlik} İçin Aksiyonlar")

        fiyat_farki = abs(degisim_yuzdesi)
        is_ust_bant_asildi = current_commodity_ratio >= ust_sinir
        is_alt_bant_asildi = current_commodity_ratio <= alt_sinir
        is_adim_asilmis_mi = fiyat_farki >= adim_araligi

        if is_ust_bant_asildi or is_alt_bant_asildi or is_adim_asilmis_mi:
            st.markdown("""
                <style>
                div.stButton > button[kind="primary"] {
                    background-color: #e74c3c !important;
                    border-color: #c0392b !important;
                    box-shadow: 0 0 10px rgba(231, 76, 60, 0.5) !important;
                    animation: pulse-red 1.5s infinite;
                }
                div.stButton > button[kind="primary"]:hover {
                    background-color: #c0392b !important;
                }
                @keyframes pulse-red {
                    0% { transform: scale(1); }
                    50% { transform: scale(1.02); box-shadow: 0 0 20px rgba(231, 76, 60, 0.8) !important; }
                    100% { transform: scale(1); }
                }
                </style>
            """, unsafe_allow_html=True)

            if is_ust_bant_asildi or is_alt_bant_asildi:
                st.error(
                    f"🚨 DİKKAT: Portföy Makro Sınırlarına Ulaştı! (Anlık: %{turkce_format(current_commodity_ratio)}) Acil DİNAMİK işlem önerilir.")
            else:
                st.warning(f"🔴 DİKKAT: Yüzdesel adım aralığına (%{turkce_format(adim_araligi)}) ulaşıldı!")

            buton_metni = "🚨 Rebalance Stratejisini Tetikle"
        else:
            buton_metni = "⚖️ Rebalance Stratejisini Tetikle"

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("📡 Piyasayı Yenile", use_container_width=True):
                yeni_fiyat = get_commodity_price(sembol)
                if yeni_fiyat:
                    st.session_state.guncel_fiyat = yeni_fiyat
                    st.rerun()

        with col_btn2:
            if st.button(buton_metni, type="primary", use_container_width=True):
                yeni_hedef_oran = st.session_state.hedef_oran
                is_macro = False

                # 1. ÖNCELİK: MAKRO TETİKLEYİCİLER (Anlık Orana Duyarlı)
                if current_commodity_ratio >= ust_sinir:
                    yeni_hedef_oran = st.session_state.hedef_oran - oran_degisim_ust
                    is_macro = True
                elif current_commodity_ratio <= alt_sinir:
                    yeni_hedef_oran = st.session_state.hedef_oran + oran_degisim_alt
                    is_macro = True

                # 2. ÖNCELİK: İŞLEMİ GERÇEKLEŞTİR
                if is_macro or is_adim_asilmis_mi:
                    hedef_emtia_degeri = (yeni_hedef_oran * current_total_capital) / 100
                    fark_dolar = hedef_emtia_degeri - current_commodity_value
                    islem_miktari_adet = fark_dolar / st.session_state.guncel_fiyat

                    if islem_miktari_adet > 0:
                        islem_turu = "DİNAMİK ALIM 🟢" if is_macro else "ALIM 🟢"
                        islem_miktari = islem_miktari_adet
                        islem_degeri = fark_dolar
                    elif islem_miktari_adet < 0:
                        islem_turu = "DİNAMİK SATIM 🔴" if is_macro else "SATIM 🔴"
                        islem_miktari = abs(islem_miktari_adet)
                        islem_degeri = abs(fark_dolar)
                    else:
                        st.info("İşlem gerektirecek bir oran farkı oluşmadı.")
                        st.stop()

                    # Cüzdanı Güncelle
                    st.session_state.nakit -= fark_dolar
                    st.session_state.emtia_miktari += islem_miktari_adet
                    new_capital = st.session_state.nakit + (
                                st.session_state.emtia_miktari * st.session_state.guncel_fiyat)

                    log_kaydi = {
                        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Varlık": secilen_varlik,
                        "Eski Fiyat": round(st.session_state.referans_fiyat, 2),
                        "Yeni Fiyat": round(st.session_state.guncel_fiyat, 2),
                        "İşlem Türü": islem_turu,
                        "İşlem Miktarı": round(islem_miktari, 4),
                        "İşlem Tutarı": round(islem_degeri, 2),
                        "Yeni Sermaye": round(new_capital, 2),
                        "Hedef Oran": f"%{yeni_hedef_oran}",
                        "Yeni Emtia Miktarı": round(st.session_state.emtia_miktari, 4)
                    }
                    islem_kaydet_csv(log_kaydi)

                    st.session_state.referans_fiyat = st.session_state.guncel_fiyat
                    st.session_state.ana_sermaye = new_capital
                    st.session_state.hedef_oran = yeni_hedef_oran
                    st.success(
                        f"✔️ {islem_turu} Başarılı! Miktar: {round(islem_miktari, 4)} | Yeni Oran: %{turkce_format(yeni_hedef_oran)}")
                    st.rerun()
                else:
                    st.info("Henüz işlem şartları sağlanmadı.")

        st.divider()
        with st.expander("🛠️ Manuel Oran Değişimi", expanded=False):
            st.markdown("Emtia oranında manuel bir değişiklik yapmak istiyorsanız buradan güncelleyebilirsiniz.")
            yeni_manuel_oran = st.number_input("Yeni Emtia Oranını Giriniz (%)", min_value=1.0, max_value=100.0,
                                               value=st.session_state.hedef_oran, step=1.0)
            if st.button("🔄 Oranı Manuel Güncelle", type="secondary"):
                if yeni_manuel_oran != st.session_state.hedef_oran:
                    yeni_emtia_hedefi = (yeni_manuel_oran * current_total_capital) / 100
                    fark_dolar = yeni_emtia_hedefi - current_commodity_value
                    islem_miktari_adet = fark_dolar / st.session_state.guncel_fiyat

                    islem_turu = "MANUEL ALIM 🟢" if fark_dolar > 0 else "MANUEL SATIM 🔴"
                    st.session_state.nakit -= fark_dolar
                    st.session_state.emtia_miktari += islem_miktari_adet

                    log_kaydi_manuel = {
                        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Varlık": secilen_varlik,
                        "Eski Fiyat": round(st.session_state.guncel_fiyat, 2),
                        "Yeni Fiyat": round(st.session_state.guncel_fiyat, 2),
                        "İşlem Türü": islem_turu,
                        "İşlem Miktarı": round(abs(islem_miktari_adet), 4),
                        "İşlem Tutarı": round(abs(fark_dolar), 2),
                        "Yeni Sermaye": round(current_total_capital, 2),
                        "Hedef Oran": f"%{yeni_manuel_oran}",
                        "Yeni Emtia Miktarı": round(st.session_state.emtia_miktari, 4)
                    }
                    islem_kaydet_csv(log_kaydi_manuel)
                    st.session_state.hedef_oran = yeni_manuel_oran
                    st.session_state.ana_sermaye = current_total_capital
                    st.success("Portföy yeni orana eşitlendi!")
                    st.rerun()

    with tab2:
        st.subheader(f"📊 {secilen_varlik} Raporu")
        if os.path.isfile(DOSYA_YOLU):
            df = pd.read_csv(DOSYA_YOLU)
            df_secilen = df[df['Varlık'] == secilen_varlik]
            if not df_secilen.empty:
                st.dataframe(df_secilen.style.highlight_max(axis=0), use_container_width=True)
                csv_data = df_secilen.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Bu Raporu CSV Olarak İndir", data=csv_data,
                                   file_name=f"{secilen_varlik}_raporu.csv", mime="text/csv")
            else:
                st.info("Bu varlık için henüz işlem yok.")
        else:
            st.info("Henüz kaydedilmiş bir geçmiş bulunmuyor.")

    with tab3:
        st.subheader("🛠️ Veritabanı Kontrol Merkezi")
        if os.path.isfile(DOSYA_YOLU):
            df_all = pd.read_csv(DOSYA_YOLU)
            edited_df = st.data_editor(df_all, num_rows="dynamic", use_container_width=True, key="data_editor")
            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Yapılan Değişiklikleri Kaydet", type="primary", use_container_width=True):
                    edited_df.to_csv(DOSYA_YOLU, index=False)
                    st.success("Değişiklikler veritabanına yazıldı!")
            with col_del:
                if st.button("🚨 TÜM GEÇMİŞİ SIFIRLA", type="secondary", use_container_width=True):
                    os.remove(DOSYA_YOLU)
                    st.success("Veritabanı silindi!")
                    st.rerun()
        else:
            st.info("CSV dosyası henüz oluşturulmamış.")
else:
    st.info("👈 Başlamak için ayarlarınızı yapın ve 'Sistemi Başlat' butonuna tıklayın.")
