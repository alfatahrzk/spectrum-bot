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
    
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error("⚠️ Secrets durung lengkap! Pastikno API Key & Token ana nang Streamlit Cloud.")
    st.stop()

# --- 2. DEFINISI TOOLS (SAMA PERSIS) ---
@tool
def cari_produk(query: str):
    """
    Gunakan alat ini untuk mencari informasi harga, deskripsi, atau daftar layanan.
    Input: Kata kunci produk (misal: 'banner', 'kartu nama') atau 'semua' untuk lihat semua daftar.
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
            hasil_teks += f"- {item['nama_produk']}: Rp{item['harga_satuan']} per {item['satuan']}. ({item['deskripsi']})\n"
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

tools = [cari_produk, cek_status_order, buat_pesanan]

# --- 3. LOGIKA AGEN TELEGRAM ---
user_sessions = {}

def get_agent_executor(chat_id, model_type):
    if model_type == "Google Gemini Flash":
        # Otak 1: Gemini (Gratis & Banter)
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
            google_api_key=st.secrets["GOOGLE_API_KEY"]
        )
    else:
        # Otak 2: Groq Llama 3 (Default - Pinter Pol)
        # Iso ganti 70b dadi 8b nek pengen irit
        llm = ChatGroq(
            temperature=0, 
            model_name="llama-3.3-70b-versatile", 
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
           2. Jika produk TIDAK ADA: Katakan "Maaf kami belum melayani cetak [produk itu]." STOP.
           3. Jika produk ADA: 
              - Jelaskan spesifikasi bahan.
              - HITUNG TOTAL HARGA (Harga Satuan x Jumlah).
              - Tanyakan: "Apakah harganya cocok, Kak?"
        
        PHASE 2: SAAT USER BILANG SETUJU / "GASS" / DEAL
           1. CEK DULU: Apakah user sudah menyebutkan namanya di chat sebelumnya?
           2. JIKA NAMA BELUM DIKETAHUI:
              - JANGAN panggil tool 'buat_pesanan'.
              - TANYA DULU: "Siap Kak! Boleh tahu pesanan ini atas nama siapa?"
              - STOP, tunggu jawaban user.
           3. JIKA NAMA SUDAH DIKETAHUI:
              - Langsung panggil tool 'buat_pesanan'.
        
        PHASE 3: LAIN-LAIN
           - Gunakan tool 'cek_status_order' untuk cek resi.
           - Gunakan istilah "Nomor Order".
           - Jawab dengan luwes, tidak kaku, layaknya manusia.
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
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
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
    """Fungsi Utama Bot Telegram (Fixed Version)"""
    # 1. Build Aplikasi
    application = ApplicationBuilder().token(telegram_token).build()
    
    # 2. Tambah Handler
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # 3. KUNCI RAHASIA: Allow nested loop
    nest_asyncio.apply()
    
    # --- BAGIAN IKI SING DIBENERNO ---
    print("🔄 Melakukan inisialisasi...")
    await application.initialize() # <--- PEMANASAN DISIK
    await application.start()      # <--- NYALAKNO MESIN
    
    print("🚀 Mulai Polling (Narik Pesan)...")
    await application.updater.start_polling() # <--- LAGI MLAYU
    
    # Trik ben gak mandheg (Infinite Wait)
    print("✅ Bot Telegram Berjalan! (Jangan tutup tab ini)")
    while True:
        await asyncio.sleep(3600) # Turu sedilut tapi melek terus

# --- 4. TAMPILAN STREAMLIT (FAKE UI) ---
# --- TAMPILAN UI ---
st.title("🤖 Spectrum Bot Server Controller")

# 1. PILIH OTAK (Dropdown)
pilihan_model = st.selectbox(
    "Pilih Otak Bot:",
    ("Groq Llama 3", "Google Gemini Flash"),
    index=0
)
st.caption(f"Model sing dipilih: **{pilihan_model}**")

# Update variabel global sadurunge bot mlaku
CURRENT_MODEL = pilihan_model 

st.write("---")

# 2. TOMBOL START
if st.button("Jalankan Bot Telegram"):
    st.info(f"🚀 Menjalankan Bot menggunakan mesin: {CURRENT_MODEL}...")
    
    # Kunci pilihan model menyang global variable maneh (ben yakin)
    CURRENT_MODEL = pilihan_model 
    
    with st.spinner("Bot sedang aktif..."):
        asyncio.run(start_bot())