import streamlit as st
import pandas as pd
import asyncio
import threading
from database import DatabaseManager
from dotenv import load_dotenv
from llm_service import LLMService
from bot import TelegramBot
import os

# Load env variables (kanggo lokal)
load_dotenv()

# ==========================================
# 🧠 INISIALISASI DATABASE (Wajib Paling Awal)
# ==========================================
@st.cache_resource
def get_db_manager():
    """
    Inisialisasi Database Manager sepisan tok.
    Ngawe os.environ.get ben aman nang thread.
    """
    try:
        # Ngirim st.secrets lan os.environ.get menyang __init__ DatabaseManager
        db_instance = DatabaseManager(st_secrets=st.secrets, os_getenv_func=os.environ.get)
        db_instance.get_all_products() # Tes koneksi
        return db_instance
    except Exception as e:
        st.error(f"❌ Gagal konek DB. Cek Secrets/Koneksi: {e}")
        st.stop()
        
# Instance DB sing dinggo kabeh Dashboard
db = get_db_manager() 

# ==========================================
# 🤖 BACKGROUND BOT RUNNER (Final Version)
# ==========================================
@st.cache_resource
def start_bot_background():
    """
    Njalanno Bot Telegram nang Thread terpisah.
    Fungsi iki ora nampa parameter ben Streamlit ora error Caching.
    De'e bakal nggunakake variabel global 'db'.
    """
    # 1. Cek Token
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        token = st.secrets.get("TELEGRAM_TOKEN")
    
    if not token:
        return "❌ Token TELEGRAM Gak Onok!"

    def runner():
        # Jupuk instance DB global
        global db 
        
        llm_srv = LLMService("Groq Llama 3") 
        
        # Kirim instance database global 'db' menyang Bot
        # Iki ngatasi masalah UnhashableParamError
        bot = TelegramBot(token, llm_srv, db) 
        
        # Jalanno Bot nang Event Loop dewe
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Panggil run nggawe loop.run_until_complete()
            loop.run_until_complete(bot.run())
        except Exception as e:
            print(f"FATAL BOT THREAD ERROR: {e}")

    # Gawe Thread (jalur)
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    
    return "✅ Bot Telegram Berjalan di Background!"

# Jalankan Bot Otomatis
status_bot = start_bot_background()


# ==========================================
# 🖥️ ADMIN DASHBOARD (UI)
# ==========================================
class AdminDashboard:
    def __init__(self):
        st.set_page_config(page_title="Spectrum Admin", layout="wide", page_icon="🖨️")
        
    def render_sidebar(self):
        with st.sidebar:
            st.header("🖨️ Spectrum Admin")
            
            # Indikator Status Bot
            if "Berjalan" in status_bot:
                st.success(status_bot)
            else:
                st.error(status_bot)
            
            st.info("Bot mlaku otomatis. Sampeyan fokus ngatur data wae nang kene.")
            
            if st.button("🔄 Refresh Data"):
                st.rerun()

    def render_orders_tab(self):
        st.subheader("📦 Manajemen Order")
        res = db.get_all_orders()
        
        if res.data:
            df = pd.DataFrame(res.data)
            st.dataframe(df)
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                list_order = df['nomor_order'].tolist() if not df.empty else []
                oid = st.selectbox("Pilih Order:", list_order) if list_order else None
            with c2:
                stat = st.selectbox("Status Baru:", ["Lunas", "Proses Cetak", "Selesai", "Diambil", "Batal"])
            with c3:
                st.write(""); st.write("")
                if st.button("Simpan Status") and oid:
                    db.update_order_status(oid, stat)
                    st.success("Status Updated!")
                    st.rerun()
        else:
            st.info("Belum ada orderan masuk.")

    def render_products_tab(self):
        st.subheader("🏷️ Katalog Produk")
        res = db.get_all_products()
        if res.data: st.dataframe(pd.DataFrame(res.data))
        
        with st.expander("Tambah Produk"):
            with st.form("add_prod"):
                nama = st.text_input("Nama")
                harga = st.number_input("Harga", step=1000)
                satuan = st.text_input("Satuan")
                bahan = st.text_input("Bahan")
                if st.form_submit_button("Simpan"):
                    db.add_product({"nama_produk": nama, "harga_satuan": harga, "satuan": satuan, "bahan": bahan})
                    st.success("Produk Masuk!")
                    st.rerun()

    def render_faq_tab(self):
        st.subheader("❓ FAQ Toko")
        res = db.get_all_faq()
        if res.data: st.dataframe(pd.DataFrame(res.data))
        
        with st.expander("Tambah FAQ"):
            with st.form("add_faq"):
                q = st.text_input("Tanya")
                a = st.text_area("Jawab")
                if st.form_submit_button("Simpan"):
                    db.add_faq({"pertanyaan": q, "jawaban": a})
                    st.success("FAQ Saved!")
                    st.rerun()

    def main(self):
        self.render_sidebar()
        st.title("🖨️ Spectrum Digital - Professional Dashboard")
        t1, t2, t3 = st.tabs(["Orders", "Products", "FAQ"])
        
        with t1: self.render_orders_tab()
        with t2: self.render_products_tab()
        with t3: self.render_faq_tab()

if __name__ == "__main__":
    app = AdminDashboard()
    app.main()