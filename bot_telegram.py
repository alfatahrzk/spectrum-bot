import os
import logging
import datetime
from dotenv import load_dotenv

# Telegram Libs
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# LangChain & Supabase Libs (Sama kayak app.py)
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from supabase import create_client, Client

# 1. LOAD API KEYS
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. DEFINISI TOOLS (COPAS DARI APP.PY - PERSIS)
@tool
def cari_produk(query: str):
    """Cari info produk. Input: nama produk atau 'semua'."""
    try:
        query_lower = query.lower()
        if query_lower in ["semua", "produk", "apa aja", "list", "menu", "layanan"]:
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
    """Buat order baru setelah deal."""
    now = datetime.datetime.now()
    nomor_order = f"ORDER-{now.strftime('%y%m%d%H%M%S')}"
    try:
        data_insert = {
            "nomor_order": nomor_order,      
            "nama_pelanggan": nama_pelanggan,
            "status_order": "Menunggu Pembayaran",
            "total_biaya": 0 
        }
        supabase.table('orders').insert(data_insert).execute()
        return f"✅ Sukses! Order: {nomor_order}. Atas nama {nama_pelanggan}. Silakan transfer ke BCA 123456."
    except Exception as e: return f"Gagal simpan: {e}"

@tool
def cek_status_order(nomor_order: str):
    """Cek status order."""
    try:
        response = supabase.table('orders').select("*").eq('nomor_order', nomor_order).execute()
        data = response.data
        if not data: return "Nomor order tidak ditemukan."
        o = data[0]
        return f"Status {o['nomor_order']} ({o['nama_pelanggan']}): {o['status_order']}."
    except Exception as e: return f"Error DB: {e}"

tools = [cari_produk, cek_status_order, buat_pesanan]

# 3. MEMORY GLOBAL (Ganti Session State)
# Format: { chat_id_telegram: [list_message] }
user_sessions = {}

def get_agent_executor(chat_id):
    """Mbangun agen + njupuk memory user"""
    llm = ChatGroq(temperature=0, model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
        Kamu adalah SpectrumBot di Telegram. 
        SOP: 
        1. Cek produk dulu. 
        2. Hitung total. 
        3. Deal -> Tanya Nama -> Buat Order.
        4. Kamus: 'gass'='setuju'.
        Jawab singkat padat karena ini chat HP.
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# 4. HANDLER TELEGRAM
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respon pas user ketik /start"""
    await update.message.reply_text("Halo! 👋 Saya SpectrumBot. Mau cetak apa hari ini?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Otak utama: Nampa pesan -> Mikir -> Mbales"""
    user_text = update.message.text
    chat_id = update.effective_chat.id
    
    # 1. Cek Memory User
    if chat_id not in user_sessions:
        user_sessions[chat_id] = [] # Inisialisasi memory nek user anyar
    
    history = user_sessions[chat_id]
    
    # 2. Kirim "Sedang mengetik..." biar keren
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # 3. Proses Agent
    print(f"📩 Pesan dari {chat_id}: {user_text}") # Log terminal
    
    agent = get_agent_executor(chat_id)
    
    # Tambah chat user ke memory
    history.append(HumanMessage(content=user_text))
    
    try:
        # Invoke Agent
        response = await agent.ainvoke({ # Pake ainvoke (Async) buat Telegram
            "input": user_text,
            "chat_history": history
        })
        
        bot_reply = response["output"]
        
        # Tambah jawaban bot ke memory
        history.append(AIMessage(content=bot_reply))
        
        # Kirim Balasan ke Telegram
        await update.message.reply_text(bot_reply)
        
    except Exception as e:
        await update.message.reply_text(f"Waduh, error Baginda: {e}")

# 5. RUN BOT
if __name__ == '__main__':
    print("🚀 SPECTRUM TELEGRAM BOT AKTIF!")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    application.run_polling()