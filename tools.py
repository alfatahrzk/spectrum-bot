import os
import urllib.parse
from langchain_core.tools import tool
from qdrant_client import QdrantClient
# Ganti menyang HuggingFace supaya ora kena limit API Google (429 Error)
from langchain_community.embeddings import HuggingFaceEmbeddings 

# ==========================================
# 📡 INISIALISASI KONEKSI
# ==========================================

# Inisialisasi Qdrant Cloud
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"), 
    api_key=os.getenv("QDRANT_API_KEY")
)

# Inisialisasi Embeddings Lokal (Gratis & Tanpa Limit)
# WAJIB: Kudu padha karo sing digunakake nang script upload_to_qdrant.py
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 1. Variabel Global kanggo Database Relasional (Supabase)
GLOBAL_DB_INSTANCE = None 

def set_global_db(db_manager):
    """
    Nyuntik instance DatabaseManager saka app.py menyang tools.
    """
    global GLOBAL_DB_INSTANCE
    GLOBAL_DB_INSTANCE = db_manager

# ==========================================
# 🧰 DAFTAR TOOLS (Fungsi Bot)
# ==========================================

@tool
def cari_produk(query: str):
    """
    PRIORITAS UTAMA. Gunakan jika user tanya HARGA, BAHAN, atau SPESIFIKASI produk.
    Contoh: 'Berapa harga banner?', 'Ada stiker apa saja?'
    """
    if GLOBAL_DB_INSTANCE is None:
        return "Error: Database instance belum terhubung."
        
    res = GLOBAL_DB_INSTANCE.search_products(query)
    
    if res is None:
        return "SYSTEM ERROR: Gagal mengakses database produk."
    
    if not res.data: 
        return "Info: Produk sing mbok cari gak ketemu nang katalog."
    
    text = "Daftar Produk & Harga:\n"
    for item in res.data:
        harga = "{:,}".format(item['harga_satuan']).replace(',', '.')
        text += f"- {item['nama_produk']}: Rp{harga} /{item['satuan']} (Bahan: {item.get('bahan','-')})\n"
    return text

@tool
def konsultasi_cetak(query: str):
    """
    Gunakan tool ini UNTUK MENJAWAB pertanyaan teknis/konsultasi mengenai:
    - Detail kelebihan/kekurangan bahan (Art Paper, PVC, dll).
    - Ukuran cetak (A3+, A4, A5, B4, dll).
    - Prosedur kirim file lan estimasi waktu pengerjaan/jilid.
    """
    try:
        # Ngowahi pitakon dadi vektor nggunakake HuggingFace
        query_vector = embeddings.embed_query(query)

        # Golek data sing paling mirip nang Qdrant Cloud
        search_result = qdrant_client.search(
            collection_name="spectrum_knowledge",
            query_vector=query_vector,
            limit=3 
        )

        if not search_result:
            return "Maaf, informasi teknis mengenai hal tersebut belum tersedia di database konsultasi kami."

        # Gabungno konteks hasil pencarian
        context = "\n".join([res.payload['content'] for res in search_result])
        return f"Informasi Teknis (RAG):\n{context}"

    except Exception as e:
        return f"Terjadi kesalahan saat mengakses basis pengetahuan: {str(e)}"

@tool
def generate_whatsapp_checkout(ringkasan_pesanan: str):
    """
    Gunakan HANYA jika customer sudah FIX ingin membeli (setuju harga & spesifikasi).
    Mengahasilkan link chat langsung ke WhatsApp Admin.
    """
    wa_number = "6281234567890" # Ganti karo nomer WA tokomu
    pesan = f"Halo Spectrum, saya mau pesan:\n\n{ringkasan_pesanan}\n\nMohon bantu proses ya Kak."
    link = f"https://wa.me/{wa_number}?text={urllib.parse.quote(pesan)}"
    return f"Sipp Kak! Klik link iki kanggo checkout via WhatsApp Admin: {link}"

@tool
def cek_status_order(nomor_order: str):
    """Gunakan untuk mengecek status pengerjaan pesanan menggunakan Nomor Order."""
    if GLOBAL_DB_INSTANCE is None:
        return "Error: Database instance belum terhubung."

    res = GLOBAL_DB_INSTANCE.check_order_status(nomor_order)
    if not res or not res.data: 
        return f"Maaf Kak, Nomor Order '{nomor_order}' ora ditemokake."
    
    o = res.data[0]
    return f"Status Order {o['nomor_order']}: {o['status_order']}. (Update terakhir: {o.get('updated_at', '-')})"

# Export list tools supaya bisa diwaca dening LLMService
bot_tools = [cari_produk, cek_status_order, generate_whatsapp_checkout, konsultasi_cetak]