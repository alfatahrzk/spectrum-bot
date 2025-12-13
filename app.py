import streamlit as st
import pandas as pd
import asyncio
from database import db  # Import Database
from llm_service import LLMService # Import LLM
from bot import TelegramBot # Import Bot Class

class AdminDashboard:
    """Mengelola Tampilan Web Admin."""
    
    def __init__(self):
        st.set_page_config(page_title="Spectrum Admin", layout="wide", page_icon="🖨️")
        
    def render_sidebar(self):
        with st.sidebar:
            st.header("🤖 Control Panel")
            model = st.selectbox("Model AI:", ("Groq Llama 3", "Google Gemini Flash"))
            
            if st.button("▶️ START BOT", type="primary"):
                st.success(f"Menjalankan bot dengan {model}...")
                
                # Dependency Injection
                llm_srv = LLMService(model)
                bot = TelegramBot(st.secrets["TELEGRAM_TOKEN"], llm_srv)
                
                with st.spinner("Bot aktif... Cek terminal untuk logs."):
                    asyncio.run(bot.run())

    def render_orders_tab(self):
        st.subheader("📦 Manajemen Order")
        if st.button("🔄 Refresh"): st.rerun()
        
        res = db.get_all_orders()
        if res.data:
            df = pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                # Handle error nek data kosong
                list_order = df['nomor_order'].tolist() if not df.empty else []
                if list_order:
                    oid = st.selectbox("Pilih Order:", list_order)
                else: oid = None
                
            with c2:
                stat = st.selectbox("Status Baru:", ["Lunas", "Proses Cetak", "Selesai", "Diambil", "Batal"])
            with c3:
                st.write(""); st.write("")
                if st.button("Simpan Status") and oid:
                    db.update_order_status(oid, stat)
                    st.success("Status Updated!")
                    st.rerun()
        else:
            st.info("Data kosong.")

    def render_products_tab(self):
        st.subheader("🏷️ Katalog Produk")
        res = db.get_all_products()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)
        
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
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)
        
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