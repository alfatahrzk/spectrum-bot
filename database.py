import streamlit as st
import datetime
import os
from supabase import create_client, Client

class DatabaseManager:
    """Mengelola semua interaksi dengan Database Supabase."""
    
    def __init__(self):
        try:
            # Ganti st.secrets dadi os.getenv
            self.url = os.getenv("SUPABASE_URL")
            self.key = os.getenv("SUPABASE_KEY")
            # Fallback nek os.getenv kosong (misal tetep lewat streamlit cloud)
            if not self.url: self.url = st.secrets["SUPABASE_URL"]
            if not self.key: self.key = st.secrets["SUPABASE_KEY"]
                
            self.client: Client = create_client(self.url, self.key)

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