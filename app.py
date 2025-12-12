import streamlit as st
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from supabase import create_client, Client
import os

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
def cek_status_order(nomor_resi: str):
    """
    Gunakan alat ini untuk mengecek status pesanan berdasarkan nomor resi.
    Input: Nomor resi (contoh: 'SPC-001').
    """
    try:
        response = supabase.table('orders').select("*")\
            .eq('nomor_resi', nomor_resi).execute()
        
        data = response.data
        if not data:
            return "Nomor resi tidak ditemukan. Mohon cek kembali."
        
        order = data[0]
        return f"Status Order {order['nomor_resi']} ({order['nama_pelanggan']}): {order['status_order']}. Total: Rp{order['total_biaya']}."
    except Exception as e:
        return f"Error database: {e}"

tools = [cari_produk, cek_status_order]

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
        ATURAN:
        1. Gunakan 'cari_produk' untuk cek harga.
        2. Gunakan 'cek_status_order' untuk cek resi.
        3. Jika alat error/kosong, katakan jujur ke user.
        4. Jawab singkat dan ramah.
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