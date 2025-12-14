import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from langchain.agents import AgentExecutor, create_tool_calling_agent # <<< Kembali ke tool_calling
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tools import bot_tools, set_global_db 
from langchain.agents import initialize_agent, AgentType

class LLMService:
    """Mengelola Model AI (Groq/Gemini) dan Agent."""

    def __init__(self, model_choice):
        self.model_choice = model_choice
        self.google_key = os.getenv("GOOGLE_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

    def _get_llm(self):
        # [KUNCI STABILITAS]: Kita prioritize Gemini Flash (lebih stabil utk tool calling Langchain)
        # Nggawe Gemini Flash dadi default (meskipun model_choice Groq)
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            google_api_key=self.google_key,
            safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
        )

    # [FIX]: Agent sing paling stabil nggawe Gemini
    def get_executor(self, db_manager_instance): 
        
        # 1. Suntik Database menyang Tools
        set_global_db(db_manager_instance) 

        llm = self._get_llm()
        
        # 2. Gawe Prompt Sistem/SOP
        prompt = ChatPromptTemplate.from_messages([
        ("system", """
        Kamu adalah 'SpectrumBot', Customer Service andalan Spectrum Digital Printing yang cerdas, gaul, tapi tetap sopan.
        
        ATURAN KALKULASI HARGA (WAJIB DILAKUKAN):
                    - Sebelum memanggil 'buat_pesanan', kamu WAJIB menghitung total biaya.
                    - Total Biaya = Harga Satuan Produk x Jumlah Pesanan.
                    - Kirim hasil perhitungan itu ke parameter 'total_biaya' di tool 'buat_pesanan'.

        KAMUS BAHASA GAUL (PENTING):
        - Jika user bilang: "gass", "sikat", "bungkus", "lanjut", "kuy", "ok", "y", "mau" -> ARTINYA ADALAH "SETUJU/DEAL".

        INFORMASI UMUM:
        # (Informasi Toko tetep padha)
        
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
        
        # 3. Nggawe Agent Tool Calling (Paling cocok karo prompt lan history chat)
        agent = create_tool_calling_agent(llm, bot_tools, prompt)
        return AgentExecutor(agent=agent, tools=bot_tools, verbose=True, handle_parsing_errors=True)