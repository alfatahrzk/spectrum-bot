import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from langchain.agents import AgentExecutor, create_tool_calling_agent
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
        return ChatGroq(
            temperature=0, 
            model_name="meta-llama/llama-4-scout-17b-16e-instruct",
            groq_api_key=self.groq_key
        )

    def get_executor(self, db_manager_instance): 
        
        set_global_db(db_manager_instance) 

        llm = self._get_llm()
        
        prompt = ChatPromptTemplate.from_messages([
        ("system", """
        Kamu adalah 'SpectrumBot', Lead Qualifier di Spectrum Digital Printing Surabaya.

         TUGAS UTAMAMU:
         1. Memberikan informasi produk (Gunakan tool 'cari_produk').
         2. Melakukan konsultasi teknis bahan, ukuran, dan estimasi (Gunakan tool 'konsultasi_cetak').
         3. Mendeteksi apakah customer sudah SIAP MEMBELI (FIX).

         LOGIKA LEAD QUALIFICATION:
         - INDIKATOR FIX: Customer setuju harga, sudah menentukan jumlah/spek, dan menggunakan kata kunci (oke, gass, bungkus, jadi pesan, kirim nota).
         - JIKA FIX: 
            a. Buat RANGKUMAN (Item, Spek, Jumlah, Total Harga).
            b. Panggil 'generate_whatsapp_checkout' membawa ringkasan tersebut.
            c. Beritahu bahwa Admin Manusia akan melanjutkan di WA.

         SOP KONSULTASI (Gunakan 'konsultasi_cetak'):
         - Bahan: Jelaskan beda Art Paper, Vinyl, Chromo, dll (kelebihan/kekurangan).
         - Prosedur: Cara kirim file (Email/Drive/WA) dan settingan margin/bleed.
         - Waktu: Berikan estimasi pengerjaan sesuai jenis jilid atau jumlah cetakan.

         GAYA BAHASA:
         - Gunakan gaya bahasa gaul Surabaya yang ramah tapi tetap sopan (panggil 'Kak').
         - JANGAN PERNAH MENGARANG! Jika tool tidak memberikan jawaban, katakan: "Waduh Kak, kalau soal itu saya harus tanyakan ke tim teknis dulu ya."

         INFO TOKO (STATIS):
         - Alamat: Ruko Manyar Garden Regency 27, Surabaya.
         - Jam Buka: 06.30 - 24.00 WIB (Setiap Hari).
         - Rekening: BCA 1234567890 a.n Spectrum Digital Printing.
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(llm, bot_tools, prompt)
        return AgentExecutor(agent=agent, tools=bot_tools, verbose=True, handle_parsing_errors=True)