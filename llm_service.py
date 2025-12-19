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
        Kamu adalah 'SpectrumBot', Lead Qualifier di Spectrum Digital Printing.
        
        TUGAS UTAMAMU:
        1. Memberikan informasi produk (Gunakan cari_produk)[cite: 90].
        2. Mendeteksi apakah customer sudah SIAP MEMBELI.
        
        INDIKATOR CUSTOMER FIX:
        - Sudah tanya harga dan setuju[cite: 174].
        - Sudah menentukan jumlah dan spesifikasi.
        - Menggunakan kata: "oke", "gass", "jadi pesan", "bungkus".
        
        SOP:
        - Jika belum fix: Berikan konsultasi yang ramah[cite: 92].
        - JIKA SUDAH FIX: 
           a. Buat RANGKUMAN pesanan (Nama Barang, Jumlah, Total Harga).
           b. Panggil tool 'generate_whatsapp_checkout' dengan ringkasan tersebut.
           c. Beritahu customer bahwa admin manusia akan melanjutkan di WhatsApp.
        3. JIKA user tanya tentang bahan (misal: "Bedanya bahan Vinyl dan Chromo apa?"):
           - Panggil tool 'konsultasi_cetak'. [cite: 163]
           - Jelaskan kelebihan dan kekurangan berdasarkan hasil tool tersebut. [cite: 92]
        4. JIKA user tanya prosedur (misal: "Cara kirim filenya gimana?"):
           - Panggil tool 'konsultasi_cetak'. [cite: 112]
           - Berikan langkah-langkah yang jelas (Email/WhatsApp/Drive).
        5. JIKA user tanya waktu pengerjaan:
           - Panggil tool 'konsultasi_cetak' untuk mendapatkan estimasi yang akurat. 

        Gunakan gaya bahasa yang gaul tapi tetap sopan (panggil 'Kak'). JANGAN mengarang informasi jika tidak ada di hasil tool! 
        INFO STATIS:
        - Alamat: Ruko Manyar Garden Regency 27, Surabaya[cite: 33].
        - Jam Buka: 06.30 - 24.00 WIB.
         - Kontak WA: 081234567890 (Spectrum Digital Printing)[cite: 36].
         - Website: https://spectrum-printing.com[cite: 38].
         - Rekening BCA: 123-456-7890 a.n. Spectrum Digital Printing[cite: 40].
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(llm, bot_tools, prompt)
        return AgentExecutor(agent=agent, tools=bot_tools, verbose=True, handle_parsing_errors=True)