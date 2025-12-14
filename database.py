import streamlit as st
import datetime
import os
from supabase import create_client, Client

class DatabaseManager:
    """Mengelola semua interaksi dengan Database Supabase. 
    Wajib diinisiasi dengan st_secrets dan os_getenv.
    """
    
    def __init__(self, st_secrets=None, os_getenv_func=None):
        # Menerima data secrets saka luar (app.py)
        self.st_secrets = st_secrets
        self.os_getenv_func = os_getenv_func or os.getenv # Fungsi os.getenv utawa os.environ.get
        
        # Jupuk Kredensial
        url, key = self._get_credentials()

        if not url or not key:
            # PENTING: Aja st.error nang kene ben gak crash nek bot.py sing nyeluk
            print("❌ GAGAL KONEKSI DB: URL/Key tidak ditemukan di environment/secrets.")
            raise ConnectionError("Supabase URL/Key tidak ditemukan.")

        self.client: Client = create_client(url, key)

    def _get_credentials(self):
        """Mencari kredensial dari os.environ dulu, lalu fallback ke st.secrets."""
        
        # 1. Coba dari OS ENV (Kanggo Bot.py utawa Streamlit Cloud)
        url = self.os_getenv_func("SUPABASE_URL")
        key = self.os_getenv_func("SUPABASE_KEY")
        
        # 2. Coba dari Streamlit Secrets (Fallback nek os.getenv kosong)
        # Nggunakake st_secrets sing dikirim saka app.py
        if not url and self.st_secrets:
            url = self.st_secrets.get("SUPABASE_URL")
            key = self.st_secrets.get("SUPABASE_KEY")
            
        return url, key

    # --- (Method CRUD dan Admin di bawah ini tetap sama) ---

    def search_products(self, query: str):
        try:
            print(f"🔍 [DB] Searching Product: {query}")
            if query.lower() in ["semua", "produk", "list", "menu"]:
                result = self.client.table('products').select("*").limit(10).execute()
            else:
                result = self.client.table('products').select("*").ilike('nama_produk', f'%{query}%').execute()
            return result
        except Exception as e:
            print(f"❌ ERROR DB (Products): {e}") 
            # Dibalekno None wae ben LLM iso lanjut
            return None

    def get_faq_summary(self):
        try:
            print(f"🔍 [DB] Fetching FAQ...")
            return self.client.table('faq').select("pertanyaan, jawaban").limit(20).execute()
        except Exception as e:
            print(f"❌ ERROR DB (FAQ): {e}")
            return None

    def create_order(self, nama, items, detail, total=0): 
        now = datetime.datetime.now()
        nomor_order = f"ORDER-{now.strftime('%y%m%d%H%M%S')}"
        data = {
            "nomor_order": nomor_order,
            "nama_pelanggan": nama,
            "status_order": "Menunggu Pembayaran",
            # [FIX]: Mbutuhake total sing dikirim saka Tool
            "total_biaya": total, 
            "detail_items": f"{items} ({detail})"
        }
        try:
            self.client.table('orders').insert(data).execute()
            return nomor_order
        except Exception: return None

    def check_order_status(self, nomor_order):
        try:
            return self.client.table('orders').select("*").eq('nomor_order', nomor_order).execute()
        except Exception: return None

    # -- Admin Methods --
    def get_all_orders(self):
        return self.client.table('orders').select("*").order('id', desc=True).execute()

    def update_order_status(self, nomor_order, status_baru):
        return self.client.table('orders').update({"status_order": status_baru}).eq("nomor_order", nomor_order).execute()

    def add_product(self, data):
        return self.client.table('products').insert(data).execute()

    def add_faq(self, data):
        return self.client.table('faq').insert(data).execute()

    def get_all_products(self):
        return self.client.table('products').select("*").order('id', desc=True).execute()

    def get_all_faq(self):
        return self.client.table('faq').select("*").order('id', desc=True).execute()