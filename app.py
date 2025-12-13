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
    """Cari info produk."""
    try:
        if query.lower() in ["semua", "produk", "apa aja", "list"]:
            response = supabase.table('products').select("*").limit(10).execute()
        else:
            response = supabase.table('products').select("*").ilike('nama_produk', f'%{query}%').execute()
        data = response.data
        if not data: return "Produk tidak ditemukan."
        res = ""
        for item in data:
            res += f"- {item['nama_produk']}: Rp{item['harga_satuan']} ({item['deskripsi']})\n"
        return res
    except Exception as e: return f"Error DB: {e}"

@tool
def buat_pesanan(nama_pelanggan: str, item: str, detail: str):
    """Buat order."""
    now = datetime.datetime.now()
    nomor_order = f"ORDER-{now.strftime('%y%m%d%H%M%S')}"
    try:
        data_insert = {"nomor_order": nomor_order, "nama_pelanggan": nama_pelanggan, "status_order": "Menunggu Pembayaran", "total_biaya": 0}
        supabase.table('orders').insert(data_insert).execute()
        return f"✅ Sukses! Order: {nomor_order}. Atas nama {nama_pelanggan}. Silakan transfer ke BCA 123456."
    except Exception as e: return f"Gagal simpan: {e}"

@tool
def cek_status_order(nomor_order: str):
    """Cek status."""
    try:
        response = supabase.table('orders').select("*").eq('nomor_order', nomor_order).execute()
        data = response.data
        if not data: return "Order tidak ditemukan."
        o = data[0]
        return f"Status {o['nomor_order']}: {o['status_order']}."
    except Exception as e: return f"Error DB: {e}"

tools = [cari_produk, cek_status_order, buat_pesanan]

# --- 3. LOGIKA AGEN TELEGRAM ---
user_sessions = {}

def get_agent_executor(chat_id):
    llm = ChatGroq(temperature=0, model_name="llama-3.3-70b-versatile", groq_api_key=groq_api_key)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Kamu SpectrumBot Telegram. SOP: 1. Cek produk. 2. Hitung total. 3. Deal -> Tanya Nama -> Buat Order. Kamus: 'gass'='setuju'. Jawab singkat."),
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
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    agent = get_agent_executor(chat_id)
    history = user_sessions[chat_id]
    history.append(HumanMessage(content=text))
    
    try:
        response = await agent.ainvoke({"input": text, "chat_history": history})
        reply = response["output"]
        history.append(AIMessage(content=reply))
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

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
st.title("🤖 Spectrum Telegram Bot Server")
st.write("Server sedang berjalan... Jangan tutup tab ini jika ingin bot tetap hidup.")
st.write("Status: **ONLINE** 🟢")

# Tombol pemicu (Trigger)
if st.button("Jalankan Bot Telegram"):
    with st.spinner("Bot Telegram sedang aktif..."):
        asyncio.run(start_bot())