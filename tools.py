from langchain_core.tools import tool
from database import db

@tool
def cari_produk(query: str):
    """
    PRIORITAS UTAMA. Gunakan alat ini HANYA jika user bertanya tentang:
    - HARGA / BIAYA cetak.
    - BAHAN / SPESIFIKASI produk (kertas, ukuran, jenis).
    - KETERSEDIAAN barang.
    Input: Nama produk (contoh: 'banner', 'kartu nama', 'stiker').
    """
    try:
        # Logika Pinter: Nek query-ne umum, tampilno kabeh/sample
        query_lower = query.lower()
        if query_lower in ["semua", "produk", "apa aja", "list", "menu", "layanan"]:
            # Jupuk 10 produk pertama
            response = supabase.table('products').select("*").limit(10).execute()
        else:
            # Cari spesifik (ilike)
            response = supabase.table('products').select("*")\
                .ilike('nama_produk', f'%{query}%').execute()
        
        data = response.data
        if not data:
            return "Maaf, produk yang dicari tidak ditemukan di katalog kami."
        
        hasil_teks = ""
        for item in data:
            harga_format = "{:,}".format(item['harga_satuan']).replace(',', '.')
            
            # Cek nek kolom bahan kosong, strip (-) ae
            bahan_info = item.get('bahan', '-') 
            
            hasil_teks += f"- {item['nama_produk']}: Rp{harga_format} /{item['satuan']}. (Spec: {bahan_info})\n"
        return hasil_teks
    except Exception as e:
        return f"Error database: {e}"


@tool
def cari_info_umum(query: str):
    """
    Gunakan alat ini jika user bertanya tentang INFORMASI TOKO (NON-PRODUK).
    Contoh: Jam Buka, Lokasi, Rekening, Cara Kirim File, Parkir, dll.
    """
    print(f"🧠 [QDRANT] Mencari konteks untuk: {query}")
    try:
        # 1. Setup Koneksi Qdrant (Cukup sekali inisialisasi sakjane, tapi kene ben aman)
        qdrant_url = st.secrets["QDRANT_URL"]
        qdrant_key = st.secrets["QDRANT_API_KEY"]
        
        # 2. Pake Model Embedding sing Podo karo pas Upload
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        # 3. Setup Vector Store
        vector_store = QdrantVectorStore.from_existing_collection(
            embedding=embeddings,
            collection_name="faq_spectrum",
            url=qdrant_url,
            api_key=qdrant_key
        )
        
        # 4. LAKUKAN PENCARIAN (Similarity Search)
        # Jupuk 3 data sing paling relevan wae (k=3)
        results = vector_store.similarity_search(query, k=3)
        
        if not results:
            return "Maaf, tidak ditemukan informasi yang relevan di database."
        
        # 5. Rangkum Hasile
        hasil_teks = "INFORMASI RELEVAN DARI DATABASE:\n"
        for doc in results:
            hasil_teks += f"{doc.page_content}\n---\n"
            
        hasil_teks += "\n(GUNAKAN DATA DI ATAS UNTUK MENJAWAB USER)"
        return hasil_teks

    except Exception as e:
        return f"Error Qdrant: {e}"


@tool
def buat_pesanan(nama_pelanggan: str, item: str, detail: str):
    """
    Gunakan alat ini HANYA jika user sudah SETUJU/CONFIRM untuk memesan barang.
    Input:
    - nama_pelanggan: Nama user.
    - item: Barang yang dipesan.
    - detail: Detail tambahan.
    """
    # 1. Generate Nomor Order
    now = datetime.datetime.now()
    nomor_order = f"ORDER-{now.strftime('%y%m%d%H%M%S')}"
    
    try:
        data_insert = {
            "nomor_order": nomor_order,      
            "nama_pelanggan": nama_pelanggan,
            "status_order": "Menunggu Pembayaran",
            "total_biaya": 0 
        }
        
        # Eksekusi Insert
        supabase.table('orders').insert(data_insert).execute()
        
        # 3. Gawe Laporan sukses
        pesan_sukses = f"""
        ✅ Pesanan Berhasil Disimpan!
        - Nomor Order: {nomor_order}
        - Atas Nama: {nama_pelanggan}
        - Item: {item}
        - Status: Menunggu Pembayaran
        
        Silakan transfer ke BCA 123-456-7890.
        Ketik "Cek pesanan {nomor_order}" untuk melihat status.
        """
        return pesan_sukses

    except Exception as e:
        return f"Gagal menyimpan ke database: {e}"

@tool
def cek_status_order(nomor_order: str):
    """
    Gunakan alat ini untuk mengecek status pesanan berdasarkan NOMOR ORDER.
    Input: Nomor Order (contoh: 'ORDER-251213...').
    """
    try:
        response = supabase.table('orders').select("*")\
            .eq('nomor_order', nomor_order).execute()
        
        data = response.data
        if not data:
            return f"Nomor Order '{nomor_order}' tidak ditemukan. Mohon cek kembali."
        
        order = data[0]
        return f"Status Order {order['nomor_order']} ({order['nama_pelanggan']}): {order['status_order']}."
    except Exception as e:
        return f"Error database: {e}"

# Export list tools
bot_tools = [cari_produk, cek_status_order, buat_pesanan, cari_info_umum]