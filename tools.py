import urllib.parse
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"), 
    api_key=os.getenv("QDRANT_API_KEY")
)

embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# 1. Variabel Global
GLOBAL_DB_INSTANCE = None 

def set_global_db(db_manager):
    """
    Fungsi iki dipanggil sepisan tok nang llm_service.py/bot.py. 
    Tujuane: Nyuntik instance DatabaseManager sing wis aman digawe nang app.py.
    """
    global GLOBAL_DB_INSTANCE
    GLOBAL_DB_INSTANCE = db_manager

@tool
def cari_produk(query: str):
    """
    PRIORITAS UTAMA. Gunakan jika user tanya HARGA, BAHAN, atau SPESIFIKASI.
    Input: Nama produk (contoh: 'banner', 'kartu nama').
    """
    # [FIX] Ganti db.search_products dadi GLOBAL_DB_INSTANCE.search_products
    res = GLOBAL_DB_INSTANCE.search_products(query)
    
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
def konsultasi_cetak(query: str):
    """
    Gunakan tool ini UNTUK MENJAWAB pertanyaan teknis pelanggan mengenai:
    - Jenis bahan cetak (Art Paper, Albatros, Vinyl, dsb).
    - Pengetahuan bahan (kelebihan, kekurangan, kegunaan).
    - Prosedur cetak dan cara pengiriman file (Email/Drive).
    - Estimasi waktu pengerjaan setiap jenis produk.
    """
    try:
        query_vector = embeddings.embed_query(query)

        search_result = qdrant_client.search(
            collection_name="spectrum_knowledge",
            query_vector=query_vector,
            limit=3 
        )

        if not search_result:
            return "Maaf, informasi teknis mengenai hal tersebut belum tersedia di database kami."

        context = "\n".join([res.payload['content'] for res in search_result])
        return f"Informasi Teknis dari Database:\n{context}"

    except Exception as e:
        return f"Terjadi kesalahan saat mengakses database konsultasi: {str(e)}"


@tool
def generate_whatsapp_checkout(ringkasan_pesanan: str):
    """
    Gunakan HANYA jika customer sudah FIX ingin membeli (setuju harga & spesifikasi).
    Input: Ringkasan detail pesanan (produk, jumlah, total harga).
    """
    wa_number = "6281234567890"
    pesan = f"Halo Spectrum, saya ingin pesan:\n\n{ringkasan_pesanan}\n\nMohon diproses ya."
    link = f"https://wa.me/{wa_number}?text={urllib.parse.quote(pesan)}"
    return f"Silakan klik link WhatsApp ini untuk menyelesaikan pembayaran: {link}"

@tool
def cek_status_order(nomor_order: str):
    """Cek status order."""
    # [FIX] Ganti db.check_order_status dadi GLOBAL_DB_INSTANCE.check_order_status
    res = GLOBAL_DB_INSTANCE.check_order_status(nomor_order)
    if not res or not res.data: return "Nomor Order tidak ditemukan."
    o = res.data[0]
    return f"Status {o['nomor_order']}: {o['status_order']}."


# Export list tools
bot_tools = [cari_produk, cek_status_order, generate_whatsapp_checkout, konsultasi_cetak]


knowledge_data = [
    # --- PENGETAHUAN BAHAN ---
    {"content": "Art Paper: Kertas licin/glossy, tipis (100-150gsm). Cocok untuk brosur dan flyer. Kelebihan: Warna tajam. Kekurangan: Sulit ditulis bolpoin."},
    {"content": "Art Carton: Mirip Art Paper tapi lebih tebal (190-310gsm). Cocok untuk kartu nama, cover buku, dan poster. Kelebihan: Kokoh dan premium."},
    {"content": "PVC: Bahan plastik keras dan tahan air. Standar digunakan untuk ID Card dan member card. Kelebihan: Sangat awet, tidak bisa sobek."},
    {"content": "HVS: Kertas standar kantor (70-100gsm). Cocok untuk fotokopi, surat, dan isi buku. Kelebihan: Murah dan mudah ditulis."},
    {"content": "Brief Card (BC): Kertas karton tidak mengkilap (matte). Sering untuk kartu stok atau undangan sederhana. Tersedia berbagai warna."},
    {"content": "Blushwhite (BW): Kertas putih bersih dengan tekstur halus namun tidak mengkilap. Biasa untuk sertifikat dan kartu nama minimalis."},
    {"content": "Concorde: Kertas bertekstur garis-garis kasar. Memberikan kesan mewah dan klasik. Sering digunakan untuk sertifikat dan piagam."},
    {"content": "Copenhagen: Fancy paper dengan tekstur unik dan serat yang terlihat jelas. Cocok untuk undangan eksklusif dan kartu nama kreatif."},
    {"content": "Standar Area Cetak: Kami menggunakan ukuran cetak A3+ dengan dimensi 320x480mm sebagai standar maksimal mesin digital kami."},
    {"content": "Layanan Penjilidan: Spectrum melayani berbagai jenis jilid, meliputi jilid lakban, softcover (lem panas), hardcover (sampul tebal), jilid spiral (kawat), dan jepret tengah atau booklet."},
    # --- PENGETAHUAN UKURAN ---
    {"content": "Ukuran A3: 29.7 x 42 cm. Ukuran standar poster kecil dan menu restoran."},
    {"content": "Ukuran A4: 21 x 29.7 cm. Ukuran standar dokumen kantor, surat, dan isi brosur."},
    {"content": "Ukuran A5: 14.8 x 21 cm. Setengah dari A4, cocok untuk flyer kecil dan buku catatan (blocknote)."},
    {"content": "Ukuran A6: 10.5 x 14.8 cm. Seperempat dari A4, biasa untuk kartu ucapan atau brosur mini."},
    {"content": "Ukuran B4: 25 x 35.3 cm. Lebih besar dari A4, sering digunakan untuk map atau dokumen khusus."},
    {"content": "Ukuran B5: 17.6 x 25 cm. Ukuran buku tulis atau agenda sekolah."},
    {"content": "Ukuran B6: 12.5 x 17.6 cm. Ukuran kecil untuk selebaran atau undangan kompak."},
    
    # --- PROSEDUR & ESTIMASI [cite: 91, 112] ---
    {"content": "Cara Pengiriman File: File bisa dikirim via Email ke spectrum.cetak@gmail.com atau Link Google Drive via WhatsApp. Pastikan format PDF atau High-Res JPG."},
    {"content": "Estimasi Cetak Warna (Tanpa Jilid): Untuk jumlah <10 lembar bisa langsung ditunggu. Jumlah <50 lembar estimasi 1 jam, <100 lembar estimasi 2 jam. Untuk pesanan >100 lembar harap hubungi admin untuk penjadwalan khusus."},
    {"content": "Catatan Kecepatan Potong: Estimasi waktu cetak dipengaruhi oleh ukuran. Semakin kecil ukuran potong (misal kartu nama/label), waktu pengerjaan akan semakin lama karena membutuhkan proses pemotongan manual yang presisi."},
    {"content": "Estimasi Tambahan Waktu Jilid (Per Buku): Jilid lakban (+10 menit), jepret tengah/booklet (+10 menit), softcover (+4 jam), dan hardcover (+24 jam untuk proses pengeringan lem)."},
    {"content": "Keunggulan Kecepatan: Proses cetak warna murni tanpa penjilidan memiliki waktu pengerjaan 10% lebih cepat dibandingkan pesanan dengan finishing."},
]