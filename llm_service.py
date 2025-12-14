import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tools import bot_tools, set_global_db

class LLMService:
    """Mengelola Model AI (Groq/Gemini) dan Agent."""

    def __init__(self, model_choice):
        self.model_choice = model_choice
        # Ganti st.secrets dadi os.getenv
        self.google_key = os.getenv("GOOGLE_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

    def _get_llm(self):
        if self.model_choice == "Google Gemini Flash":
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0,
                google_api_key=self.google_key,
                safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
            )
        else:
            return ChatGroq(
                temperature=0, 
                model_name="llama-3.3-70b-versatile", 
                groq_api_key=self.groq_key
            )

    def get_executor(self, db_manager_instance):

        set_global_db(db_manager_instance)

        llm = self._get_llm()

        from langchain.agents import initialize_agent, AgentType

        SYSTEM_PREFIX = """
        Kamu adalah 'SpectrumBot', Customer Service andalan Spectrum Digital Printing yang cerdas, gaul, tapi tetap sopan.
        
        KAMUS BAHASA GAUL (PENTING):
        - Jika user bilang: "gass", "sikat", "bungkus", "lanjut", "kuy", "ok", "y", "mau" -> ARTINYA ADALAH "SETUJU/DEAL".

        INFORMASI UMUM:
        - Nama Toko: Spectrum Digital Printing
        - Alamat: Ruko Manyar Garden Regency No. 27, Jl. Nginden Semolo No.101, Menur Pumpungan, Kec. Sukolilo,
        - Nomor Telepon: (031) 5998267
        - Rekening Bank: BCA 123-456-7890 a.n. Spectrum
        - Media Sosial: Instagram @spectrumprinting, Facebook Spectrum Digital Printing
        - Website: www.spectrumprinting.id
        - Waktu Operasional: Setiap Hari, 06.30 - 24.00 WIB
        - No. WhatsApp: 0812-3456-7890
        - Melayani pemesanan cetak online dan offline dengan pengiriman ke seluruh Indonesia.
        
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
        """

        agent = initialize_agent(
            tools=bot_tools, 
            llm=llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, 
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            # [PENTING]: Masukno SOP sistem menyang agent
            agent_kwargs={
                "prefix": SYSTEM_PREFIX
            }
        )

        return agent