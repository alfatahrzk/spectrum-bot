import streamlit as st
import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from supabase import create_client, Client
from langchain_google_genai import ChatGoogleGenerativeAI
import datetime
import os

# --- 1. SETUP KONEKSI (NGGAWE SECRETS STREAMLIT) ---
# Eling! Pas deploy engko, lebokno TELEGRAM_TOKEN nang Secrets Streamlit pisan
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    telegram_token = st.secrets["TELEGRAM_TOKEN"]
    google_api_key = st.secrets["GOOGLE_API_KEY"]
    
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error("⚠️ Secrets durung lengkap! Pastikno API Key & Token ana nang Streamlit Cloud.")
    st.stop()

# --- 2. DEFINISI TOOLS (SAMA PERSIS) ---
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
    Topik meliputi:
    - Jam Buka / Operasional / Libur.
    - Alamat / Lokasi / Map.
    - Cara Kirim File / Format File / Email.
    - Nomor Rekening / Cara Bayar / DP.
    - Pengiriman / Ekspedisi.
    Input: Kata kunci topik (contoh: 'jam buka', 'rekening', 'email').
    """
    try:
        # Cari pertanyaan sing mirip-mirip (ilike)
        response = supabase.table('faq').select("*")\
            .ilike('pertanyaan', f'%{query}%').execute()
        
        data = response.data
        
        # Nek gak nemu spesifik, coba cari sing luwih umum (opsional)
        if not data:
             # Jupuk kabeh FAQ ben LLM milih dewe (limit 5 ae ben gak boros token)
             response = supabase.table('faq').select("*").limit(5).execute()
             data = response.data

        if not data:
            return "Maaf, informasi tersebut tidak ditemukan di FAQ kami."
        
        hasil_teks = ""
        for item in data:
            hasil_teks += f"Q: {item['pertanyaan']}\nA: {item['jawaban']}\n---\n"
            
        return hasil_teks
    except Exception as e:
        return f"Error database: {e}"

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

tools = [cari_produk, cek_status_order, buat_pesanan, cari_info_umum]

# --- 3. LOGIKA AGEN TELEGRAM ---
user_sessions = {}

def get_agent_executor(chat_id, model_type):
    if model_type == "Google Gemini Flash":
        # Otak 1: Gemini (Gratis & Banter)
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            google_api_key=st.secrets["GOOGLE_API_KEY"]
        )
    else:
        # Otak 2: Groq Llama 3 (Default - Pinter Pol)
        # Iso ganti 70b dadi 8b nek pengen irit
        llm = ChatGroq(
            temperature=0, 
            model_name="llama-3.1-8b-instant", 
            groq_api_key=st.secrets["GROQ_API_KEY"]
        )
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
        Kamu adalah 'SpectrumBot', Customer Service andalan Spectrum Digital Printing yang cerdas, gaul, tapi tetap sopan.
        
        KAMUS BAHASA GAUL (PENTING):
        - Jika user bilang: "gass", "sikat", "bungkus", "lanjut", "kuy", "ok", "y", "mau" -> ARTINYA ADALAH "SETUJU/DEAL".
        
        SOP PELAYANAN (WAJIB DIPATUHI SECARA BERURUTAN):
        
        PHASE 1: SAAT USER TANYA HARGA/INGIN PESAN
           1. WAJIB panggil tool 'cari_produk' dulu.
           2. Jika produk TIDAK ADA: Katakan "Maaf kami belum melayani cetak [produk itu] Kak." STOP.
           3. Jika produk ADA: 
              - Jelaskan spesifikasi bahan.
              - HITUNG TOTAL HARGA (Harga Satuan x Jumlah).
              - Tanyakan: "Ada tambahan lain, Kak?"
           4. Jika tanya INFO UMUM (Jam buka, Lokasi, File, Rekening) -> Gunakan 'cari_info_umum'.
        
        PHASE 2: SAAT USER BILANG SETUJU / "GASS" / DEAL
           1. CEK DULU: Apakah user sudah menyebutkan namanya di chat sebelumnya?
           2. JIKA NAMA BELUM DIKETAHUI:
              - JANGAN panggil tool 'buat_pesanan'.
              - TANYA DULU: "Siap Kak! Boleh tahu pesanan ini atas nama siapa?"
              - STOP, tunggu jawaban user.
           3. JIKA NAMA SUDAH DIKETAHUI:
              - Langsung panggil tool 'buat_pesanan'.
        
        PHASE 3: LAIN-LAIN
           - Gunakan tool 'cek_status_order' untuk cek order.
           - JANGAN ngarang info toko. Cek tool 'cari_info_umum' dulu.
           - Gunakan istilah "Nomor Order".
           - Jika user cuma ketik nama barang (misal: "Poster") -> ASUMSIKAN user ingin beli, gunakan 'cari_produk'.
           - Jawab dengan luwes, tidak kaku, layaknya manusia.
           - DILARANG KERAS mengarang/membuat sendiri Nomor Order (ORDER-xxxx).
           - Nomor Order HANYA boleh disebut jika kamu sudah menerima output dari tool 'buat_pesanan'.
           - JANGAN bilang "Pesanan sudah dicatat" jika tool 'buat_pesanan' belum sukses dijalankan.
           - Jika tool error atau belum jalan, katakan: "Sebentar, saya input dulu ya..." lalu panggil toolnya.
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True, 
        max_iterations=3, 
        handle_parsing_errors=True
    )
CURRENT_MODEL = "Groq Llama 3" 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    if chat_id not in user_sessions: user_sessions[chat_id] = []
    
    # Reset command
    if text == "/reset":
        user_sessions[chat_id] = []
        await update.message.reply_text("🧠 Memori direset.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # Pake model sing dipilih nang Dropdown (Global Var)
    agent = get_agent_executor(chat_id, model_type=CURRENT_MODEL)
    
    history = user_sessions[chat_id]
    history.append(HumanMessage(content=text))
    
    try:
        response = await agent.ainvoke({"input": text, "chat_history": history})
        reply = response["output"]
        history.append(AIMessage(content=reply))
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error ({CURRENT_MODEL}): {e}")

async def start_bot():
    """Fungsi Utama Bot Telegram"""
    application = ApplicationBuilder().token(telegram_token).build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    nest_asyncio.apply()
    
    print("🔄 Inisialisasi...")
    await application.initialize()
    await application.start()
    
    print("🚀 Mulai Polling...")
    # PERBAIKAN: Hapus 'await' ing kene!
    await application.updater.start_polling(drop_pending_updates=True) 
    
    print("✅ Bot Berjalan!")
    while True:
        await asyncio.sleep(3600)

# --- 4. TAMPILAN STREAMLIT (FAKE UI) ---
# --- TAMPILAN UI ---
st.title("🤖 Spectrum Bot Controller")

# Dropdown Pemilih Otak
pilihan_model = st.selectbox(
    "Pilih Otak Bot:",
    ("Groq Llama 3", "Google Gemini Flash"),
    index=0
)
st.caption(f"Status: Menggunakan **{pilihan_model}**")

# Update Global Variable
CURRENT_MODEL = pilihan_model 

st.write("---")

if st.button("Jalankan Bot Telegram"):
    st.info(f"🚀 Menjalankan Bot dengan mesin: {CURRENT_MODEL}...")
    CURRENT_MODEL = pilihan_model 
    with st.spinner("Bot sedang aktif..."):
        asyncio.run(start_bot())