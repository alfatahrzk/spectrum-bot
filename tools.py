from langchain_core.tools import tool

GLOBAL_DB_INSTANCE = None 

# Kita ubah cara panggile:
def set_global_db(db_manager):
    """Fungsi iki dipanggil sepisan tok nang llm_service.py"""
    global GLOBAL_DB_INSTANCE
    GLOBAL_DB_INSTANCE = db_manager

@tool
def cari_produk(query: str):
    """
    PRIORITAS UTAMA. Gunakan jika user tanya HARGA, BAHAN, atau SPESIFIKASI.
    Input: Nama produk (contoh: 'banner', 'kartu nama').
    """
    res = db.search_products(query)
    
    # Cek nek ERROR (None)
    if res is None:
        return "SYSTEM ERROR: Gagal mengakses database produk. Cek Terminal untuk detail error."
    
    # Cek nek KOSONG (Data [])
    if not res.data: 
        return "Info: Produk yang dicari tidak ditemukan di database."
    
    text = ""
    for item in res.data:
        harga = "{:,}".format(item['harga_satuan']).replace(',', '.')
        text += f"- {item['nama_produk']}: Rp{harga} /{item['satuan']} (Spec: {item.get('bahan','-')})\n"
    return text

@tool
def cari_info_umum(query: str):
    """Gunakan jika user tanya INFO TOKO (Jam Buka, Lokasi, Rekening, Cara Kirim File)."""
    res = db.get_faq_summary()
    if not res or not res.data: return "Info toko belum tersedia."
    
    text = "INFORMASI TOKO (FAQ):\n"
    for item in res.data:
        text += f"Q: {item['pertanyaan']} | A: {item['jawaban']}\n"
    return text

@tool
def buat_pesanan(nama_pelanggan: str, item: str, detail: str):
    """Gunakan HANYA jika user sudah DEAL dan menyebutkan NAMA."""
    nomor = db.create_order(nama_pelanggan, item, detail)
    if nomor:
        return f"✅ Sukses! Order ID: {nomor}. Atas nama {nama_pelanggan}. Silakan transfer ke BCA 123456."
    return "Gagal membuat pesanan. Coba lagi."

@tool
def cek_status_order(nomor_order: str):
    """Cek status order."""
    res = db.check_order_status(nomor_order)
    if not res or not res.data: return "Nomor Order tidak ditemukan."
    o = res.data[0]
    return f"Status {o['nomor_order']}: {o['status_order']}."


# Export list tools
bot_tools = [cari_produk, cek_status_order, buat_pesanan, cari_info_umum]