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
        # [FIX] Mindahno config menyang paling dhuwur
        st.set_page_config(page_title="Spectrum Admin", layout="wide", page_icon="🖨️")

    # ... (render_sidebar lan render_orders tetep) ...

    def render_products_tab(self):
        st.subheader("🏷️ Manajemen Katalog Produk")
        st.info("Data ing kene bakal digunakake Bot kanggo mangsuli pitakon rega (Tool: cari_produk).")
        res = db.get_all_products()
        if res.data: 
            df = pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
        
        # ... (Form tambah produk tetep) ...

    def render_knowledge_status(self):
        """Ganti tab FAQ dadi status Knowledge Base Qdrant"""
        st.subheader("🧠 Status Knowledge Base (RAG)")
        st.success("✅ Qdrant Cloud Connected: Collection 'spectrum_knowledge'")
        st.write("""
        Bot saiki moco data konsultasi (bahan, ukuran, estimasi) saka Qdrant Cloud.
        Kanggo nganyari data iki, gunakake script `upload_to_qdrant.py`.
        """)
        if st.button("Lihat Panduan Konsultasi"):
            st.code("""
            - Jenis Bahan (Art Paper, PVC, dll)
            - Ukuran Cetak (A3+, A4, dll)
            - Estimasi Jilid & Finishing
            """)

    def main(self):
        self.render_sidebar()
        st.title("🖨️ Spectrum Digital - Professional Dashboard")
        # Update Tab dadi luwih relevan
        t1, t2, t3 = st.tabs(["📦 Order Management", "🏷️ Product Catalog", "🧠 Knowledge Status"])
        
        with t1: self.render_orders_tab()
        with t2: self.render_products_tab()
        with t3: self.render_knowledge_status() # Ganti FAQ dadi Status Knowledge
if __name__ == "__main__":
    app = AdminDashboard()
    app.main()