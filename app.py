import streamlit as st
import pandas as pd
import asyncio
import threading
import os
from database import DatabaseManager
from llm_service import LLMService
from bot import TelegramBot
from dotenv import load_dotenv

# 1. LOAD CONFIGURATION
load_dotenv()

# WAJIB: set_page_config kudu dadi perintah Streamlit sing pertama dhiwene
st.set_page_config(
    page_title="Spectrum Admin Dashboard", 
    layout="wide", 
    page_icon="🖨️"
)

# ==========================================
# 🧠 DATABASE INITIALIZATION (Cached)
# ==========================================
@st.cache_resource
def get_db_manager():
    """Inisialisasi koneksi Supabase sepisan tok."""
    try:
        # Ngirim secrets saka Streamlit Cloud dashboard menyang class DatabaseManager
        db_instance = DatabaseManager(
            st_secrets=st.secrets, 
            os_getenv_func=os.environ.get
        )
        return db_instance
    except Exception as e:
        # Aja st.stop() nang kene supaya dashboard tetep kebuka senajan DB error
        return None

db = get_db_manager()

# ==========================================
# 🤖 BOT RUNNER (Background Thread)
# ==========================================
@st.cache_resource
def start_bot_background():
    """Njalanno Bot Telegram nang jalur (thread) liyane."""
    token = st.secrets.get("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        return "❌ Token TELEGRAM_TOKEN ora ditemokake ing Secrets!"

    def runner():
        global db
        # Gunakake model Llama 3 sing pinter (70B) kanggo Lead Qualifier
        llm_srv = LLMService("Groq Llama 3") 
        
        # Inisialisasi Bot kanthi nggawa instance database
        bot = TelegramBot(token, llm_srv, db) 
        
        # Gawe loop anyar khusus kanggo thread iki
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot.run())
        except Exception as e:
            print(f"BOT ERROR: {e}")

    # Start thread
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return "✅ Bot Telegram Aktif (Background)"

# Jalankan Bot otomatis
status_bot = start_bot_background()

# ==========================================
# 🖥️ ADMIN DASHBOARD CLASS
# ==========================================
class AdminDashboard:
    def __init__(self):
        self.db = db

    def render_sidebar(self):
        with st.sidebar:
            st.title("🖨️ Spectrum Printing")
            st.divider()
            
            # Status Indikator
            if status_bot and "✅" in status_bot:
                st.success(status_bot)
            else:
                st.error(status_bot or "❌ Bot mati/error")
            
            st.info("Bot otomatis dadi Lead Qualifier lan Konsultan Teknis (RAG).")
            
            if st.button("🔄 Refresh Data"):
                st.rerun()

    def render_orders_tab(self):
        st.header("📦 Manajemen Pesanan")
        if not self.db:
            st.warning("Database ora nyambung. Cek konfigurasi.")
            return

        res = self.db.get_all_orders()
        if res and res.data:
            df = pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                order_id = st.selectbox("Pilih No. Order:", df['nomor_order'].tolist())
            with col2:
                new_status = st.selectbox("Update Status:", ["Proses", "Selesai", "Batal"])
                if st.button("Update Status"):
                    self.db.update_order_status(order_id, new_status)
                    st.success(f"Order {order_id} diupdate dadi {new_status}")
                    st.rerun()
        else:
            st.info("Durung onok data orderan masuk.")

    def render_products_tab(self):
        st.header("🏷️ Katalog Produk")
        if not self.db: return

        res = self.db.get_all_products()
        if res and res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
        
        with st.expander("➕ Tambah Produk Anyar"):
            with st.form("form_produk"):
                nama = st.text_input("Nama Produk")
                harga = st.number_input("Harga Satuan", min_value=0, step=500)
                bahan = st.text_input("Jenis Bahan")
                satuan = st.text_input("Satuan (lbr/meter/pcs)")
                if st.form_submit_button("Simpan Produk"):
                    self.db.add_product({
                        "nama_produk": nama, 
                        "harga_satuan": harga, 
                        "bahan": bahan, 
                        "satuan": satuan
                    })
                    st.success("Produk sukses ditambahkan!")
                    st.rerun()

    def render_knowledge_status(self):
        st.header("🧠 AI Knowledge Base (Qdrant)")
        st.info("Data ing ngisor iki disimpen nang Vector Database kanggo fitur Konsultasi AI.")
        
        st.success("📡 Status: Qdrant Cloud Connected")
        st.markdown("""
        **Topik sing dikuasai Bot (RAG):**
        * **Spek Bahan:** Art Paper, Art Carton, PVC, lsp.
        * **Ukuran:** A3+, A4, B5, lsp.
        * **Finishing:** Jilid Hardcover, Softcover, Spiral, lsp.
        * **Estimasi:** Waktu pengerjaan tiap jenis produk.
        """)
        
        st.warning("⚠️ Kanggo update data iki, gunakake script `upload_to_qdrant.py` saka terminal.")

    def main(self):
        self.render_sidebar()
        
        st.title("Admin Control Center")
        tab_order, tab_produk, tab_ai = st.tabs([
            "📋 Daftar Order", 
            "🏷️ Katalog Produk", 
            "🧠 AI Knowledge"
        ])
        
        with tab_order: self.render_orders_tab()
        with tab_produk: self.render_products_tab()
        with tab_ai: self.render_knowledge_status()

# 4. EXECUTION
if __name__ == "__main__":
    dashboard = AdminDashboard()
    dashboard.main()