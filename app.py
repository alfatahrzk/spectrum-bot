import streamlit as st
import pandas as pd
import asyncio
import threading
from database import DatabaseManager
from dotenv import load_dotenv
from llm_service import LLMService
from bot import TelegramBot
import os

# Load env
load_dotenv()

# ==========================================
# 🤖 BACKGROUND BOT RUNNER
# ==========================================
@st.cache_resource
def start_bot_background(db_manager_instance): # <<< TAMBAHI PARAMETER DB MANAGER
    """
    Fungsi iki mung dijalanno SEPISAN pas aplikasi start.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        token = st.secrets.get("TELEGRAM_TOKEN")
    
    if not token:
        return "❌ Token Gak Onok!"

    def runner():
        # [FIX]: llm_service kudu diinisiasi nang kene maneh amarga beda thread
        llm_srv = LLMService("Groq Llama 3") 
        
        # Kirim instance database sing wis aman digawe
        bot = TelegramBot(token, llm_srv, db_manager_instance) # <<< NGGUNAKAKE db_manager_instance
        
        # Jalanno Bot
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot.run())
        except Exception as e:
            print(f"FATAL BOT THREAD ERROR: {e}")

    # Gawe Thread
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    
    return "✅ Bot Telegram Berjalan di Background!"

# [FIX]: Panggil fungsi iki nggawe instance database sing wis digawe nang nduwur
status_bot = start_bot_background(db)


def start_bot_background():
    """
    Fungsi iki mung dijalanno SEPISAN pas aplikasi start.
    De'e bakal nggawe jalur anyar (Thread) khusus kanggo Bot Telegram.
    """
    # 1. Cek Token
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        # Fallback nek nggawe Secrets Streamlit Cloud
        token = st.secrets.get("TELEGRAM_TOKEN")
    
    if not token:
        return "❌ Token Gak Onok!"

    # 2. Siapno Bot
    def runner():
        # Pilih Model Default (Groq)
        token = os.getenv("TELEGRAM_TOKEN")
        llm_srv = LLMService("Groq Llama 3") 
        bot = TelegramBot(token, llm_srv, db_manager_thread)

        db_manager_thread = DatabaseManager(os_getenv_func=os.environ.get)
        
        # Jalanno Bot (Looping Selawase)
        # Nggawe loop anyar ben gak tabrakan karo Streamlit
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.run()) # Iki bakal blocking, tapi aman soale nang thread dewe

    # 3. Gawe Thread (Jalur Khusus)
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    
    return "✅ Bot Telegram Berjalan di Background!"

# Jalankan Bot Otomatis pas file iki dibukak
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
            st.dataframe(df) # Wis aman tanpa warning
            
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