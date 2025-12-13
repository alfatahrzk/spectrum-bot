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
# [UPDATE] Tambah Import Safety Settings ben Gemini gak manja
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
import datetime
import os

# --- 1. SETUP KONEKSI ---
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    telegram_token = st.secrets["TELEGRAM_TOKEN"]
    google_api_key = st.secrets["GOOGLE_API_KEY"]
    
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error(f"⚠️ Secrets durung lengkap! Error: {e}")
    st.stop()

# --- 2. DEFINISI TOOLS ---
@tool
def cari_produk(query: str):
    """
    PRIORITAS UTAMA. Gunakan alat ini HANYA jika user bertanya tentang:
    - HARGA / BIAYA cetak.
    - BAHAN / SPESIFIKASI produk.
    Input: Nama produk (contoh: 'banner', 'kartu nama').
    """
    try:
        query_lower = query.lower()
        if query_lower in ["semua", "produk", "apa aja", "list", "menu", "layanan"]:
            response = supabase.table('products').select("*").limit(10).execute()
        else:
            response = supabase.table('products').select("*").ilike('nama_produk', f'%{query}%').execute()
        
        data = response.data
        if not data: return "Maaf, produk tidak ditemukan."
        
        hasil_teks = ""
        for item in data:
            harga_format = "{:,}".format(item['harga_satuan']).replace(',', '.')
            bahan_info = item.get('bahan', '-') 
            hasil_teks += f"- {item['nama_produk']}: Rp{harga_format} /{item['satuan']}. (Spec: {bahan_info})\n"
        return hasil_teks
    except Exception as e: return f"Error DB: {e}"

@tool
def cari_info_umum(query: str):
    """
    Gunakan alat ini jika user bertanya tentang INFORMASI TOKO (NON-PRODUK).
    Contoh: Jam Buka, Lokasi, Rekening, Cara Kirim File.
    """
    try:
        response = supabase.table('faq').select("*").ilike('pertanyaan', f'%{query}%').execute()
        data = response.data
        if not data:
             response = supabase.table('faq').select("*").limit(5).execute()
             data = response.data
        if not data: return "Info tidak ditemukan di FAQ."
        
        hasil_teks = ""
        for item in data:
            hasil_teks += f"Q: {item['pertanyaan']}\nA: {item['jawaban']}\n---\n"
        return hasil_teks
    except Exception as e: return f"Error DB: {e}"

@tool
def buat_pesanan(nama_pelanggan: str, item: str, detail: str):
    """Buat order baru (HANYA JIKA DEAL)."""
    now = datetime.datetime.now()
    nomor_order = f"ORDER-{now.strftime('%y%m%d%H%M%S')}"
    try:
        data_insert = {"nomor_order": nomor_order, "nama_pelanggan": nama_pelanggan, "status_order": "Menunggu Pembayaran", "total_biaya": 0}
        supabase.table('orders').insert(data_insert).execute()
        return f"✅ Sukses! Order: {nomor_order}. Atas nama {nama_pelanggan}. Transfer ke BCA 123456."
    except Exception as e: return f"Gagal simpan: {e}"

@tool
def cek_status_order(nomor_order: str):
    """Cek status berdasarkan nomor order."""
    try:
        response = supabase.table('orders').select("*").eq('nomor_order', nomor_order).execute()
        data = response.data
        if not data: return "Order tidak ditemukan."
        o = data[0]
        return f"Status {o['nomor_order']} ({o['nama_pelanggan']}): {o['status_order']}."
    except Exception as e: return f"Error DB: {e}"

tools = [cari_produk, cek_status_order, buat_pesanan, cari_info_umum]

# --- 3. LOGIKA AGEN ---
user_sessions = {}
CURRENT_MODEL = "Groq Llama 3"

def get_agent_executor(chat_id, model_type):
    if model_type == "Google Gemini Flash":
        # [UPDATE] Anti-Sensor Settings
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", # Nek 2.5 isih error, otomatis fallback
            temperature=0,
            google_api_key=google_api_key,
            safety_settings={
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
    else:
        # [UPDATE] Ganti 8B (Goblok) dadi 70B (Pinter)
        llm = ChatGroq(
            temperature=0, 
            model_name="llama-3.3-70b-versatile", # <--- Iki kuncine ben ora error 400
            groq_api_key=groq_api_key
        )

    # [UPDATE] PROMPT DETAIL & ANTI-GOBLOK
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
        Kamu adalah 'SpectrumBot', Asisten Virtual Spectrum Digital Printing.
        Identitasmu: Cerdas, Teliti, dan Menggunakan Bahasa Indonesia yang Luwes (Boleh gaul tapi sopan).
        
        TUGAS UTAMA:
        Membantu pelanggan mengecek harga, info toko, dan membuat pesanan.
        
        PROSEDUR BERPIKIR (STEP-BY-STEP):
        1.  **Analisis Input:** Apa yang user cari? Produk? Info Umum? Atau mau Deal?
        2.  **Pilih Alat (Tool):**
            - Jika tanya HARGA/BAHAN -> Gunakan `cari_produk`.
            - Jika tanya LOKASI/JAM/REKENING -> Gunakan `cari_info_umum`.
            - Jika tanya STATUS -> Gunakan `cek_status_order`.
            - Jika user DEAL/SETUJU -> Cek nama dulu, baru gunakan `buat_pesanan`.
        3.  **Verifikasi Output:** Jangan pernah mengarang data. Gunakan HANYA data dari output alat.
        
        ATURAN KRUSIAL (ANTI-HALUSINASI):
        - DILARANG KERAS menyebutkan "Nomor Order" (ORDER-XXX) buatan sendiri. 
        - Nomor Order HANYA boleh diberikan jika tool `buat_pesanan` BERHASIL dijalankan.
        - Jika tool `buat_pesanan` belum dipanggil, katakan: "Mohon tunggu sebentar, saya proses pesanan kakak..."
        
        FORMAT RESPON:
        - Jika membalas hasil pencarian produk: Sebutkan Nama, Harga, dan Spesifikasi Bahan.
        - Tawarkan bantuan lanjutan di akhir chat (CTA).
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    if chat_id not in user_sessions: user_sessions[chat_id] = []
    
    if text == "/reset":
        user_sessions[chat_id] = []
        await update.message.reply_text("🧠 Memori direset.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    agent = get_agent_executor(chat_id, model_type=CURRENT_MODEL)
    history = user_sessions[chat_id]
    history.append(HumanMessage(content=text))
    
    try:
        response = await agent.ainvoke({"input": text, "chat_history": history})
        reply = response["output"]
        
        # Cek nek jawaban kosong (Gemini kadang ngene)
        if not reply or reply.strip() == "":
            reply = "Maaf kak, sinyal saya agak putus-putus. Bisa diulangi pertanyaannya? 🙏"
            
        history.append(AIMessage(content=reply))
        await update.message.reply_text(reply)
    except Exception as e:
        err_msg = str(e)
        if "404" in err_msg or "not found" in err_msg.lower():
             await update.message.reply_text("⚠️ Model error. Coba ketik /reset atau ganti model di dashboard.")
        else:
            await update.message.reply_text(f"Ada kendala teknis: {e}")

async def start_bot():
    """Fungsi Utama Bot Telegram"""
    application = ApplicationBuilder().token(telegram_token).build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    nest_asyncio.apply()
    
    print("🔄 Inisialisasi...")
    await application.initialize()
    await application.start()
    
    print("🚀 Mulai Polling...")
    # [PASTIKAN TIDAK ADA AWAIT]
    application.updater.start_polling(drop_pending_updates=True) 
    
    print("✅ Bot Berjalan!")
    while True:
        await asyncio.sleep(3600)

# --- 4. TAMPILAN UI ---
st.title("🤖 Spectrum Bot Controller")
pilihan_model = st.selectbox("Pilih Otak Bot:", ("Groq Llama 3", "Google Gemini Flash"), index=0)
st.caption(f"Status: Menggunakan **{pilihan_model}**")
CURRENT_MODEL = pilihan_model 
st.write("---")

if st.button("Jalankan Bot Telegram"):
    st.info(f"🚀 Menjalankan Bot dengan mesin: {CURRENT_MODEL}...")
    CURRENT_MODEL = pilihan_model 
    with st.spinner("Bot sedang aktif..."):
        asyncio.run(start_bot())