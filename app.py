import streamlit as st
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from supabase import create_client, Client
import os
import datetime 

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Spectrum Assistant", page_icon="🖨️")
st.title("🖨️ Spectrum Digital Printing Bot")
st.caption("Asisten Cerdas berbasis Llama 3 & Agentic RAG")

# --- 2. SETUP KONEKSI (GROQ & SUPABASE) ---
# Kita jupuk API Key teko Streamlit Secrets (Nanti kita set di Cloud)
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    
    # Konek Supabase
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error("⚠️ Secrets belum diset! Pastikan API Key ada di Streamlit Cloud.")
    st.stop()

# --- 3. DEFINISI TOOLS (ALAT) ---
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

# --- 4. MEMORY & SESSION STATE ---
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Tampilkan Chat History sing wis ana
for msg in st.session_state.chat_history:
    if isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    elif isinstance(msg, AIMessage):
        st.chat_message("assistant").write(msg.content)

# --- 5. RAKIT AGEN (OTAK) ---
# Gunakan cache_resource biar gak loading ulang tiap kali ngechat
@st.cache_resource
def get_agent():
    llm = ChatGroq(
        temperature=0, 
        model_name="llama-3.3-70b-versatile", 
        groq_api_key=groq_api_key
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
        Kamu adalah 'SpectrumBot', CS Spectrum Digital Printing.
        
        ATURAN MUTLAK:
        1. Gunakan 'cari_produk' untuk cek harga/layanan.
        2. Gunakan 'cek_status_order' untuk cek STATUS ORDER.
        3. Jika user BILANG "MAU PESAN" atau "DEAL", GUNAKAN tool 'buat_pesanan'.
           - Tanyakan nama user dulu jika belum tahu.
        4. Jika user tanya "jual apa aja", panggil 'cari_produk' dengan input "semua".
        5. Gunakan istilah "Nomor Order" (bukan Resi/Antrian).
        6. Jawab dalam Bahasa Indonesia yang ramah dan singkat.
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
agent_executor = get_agent()

# --- 6. INPUT CHAT USER ---
user_input = st.chat_input("Ketik pertanyaanmu di sini...")

if user_input:
    # 1. Tampilkan pesan user
    st.chat_message("user").write(user_input)
    st.session_state.chat_history.append(HumanMessage(content=user_input))

    # 2. Bot Mikir
    with st.chat_message("assistant"):
        with st.spinner("Sedang mengecek data..."):
            try:
                # Invoke Agent kanthi MEMORY
                response = agent_executor.invoke({
                    "input": user_input,
                    "chat_history": st.session_state.chat_history # <--- KIRIM SANGU MEMORI
                })
                bot_reply = response["output"]
                st.write(bot_reply)
                
                # Simpan jawaban bot ke history
                st.session_state.chat_history.append(AIMessage(content=bot_reply))
            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")