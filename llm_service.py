import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from langchain.agents import initialize_agent, AgentType, AgentExecutor
from tools import bot_tools, set_global_db 

class LLMService:
    """Mengelola Model AI (Groq/Gemini) dan Agent."""

    def __init__(self, model_choice):
        self.model_choice = model_choice
        self.google_key = os.getenv("GOOGLE_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

    def _get_llm(self):
        # [FIX]: Amarga kita nggawe AgentType.OPENAI_FUNCTIONS, kita kudu milih model sing cocok
        if self.model_choice == "Google Gemini Flash":
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0,
                google_api_key=self.google_key,
                safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
            )
        else:
            # Model Groq iki ndhukung fungsi (tool calling)
            return ChatGroq(
                temperature=0, 
                model_name="llama-3.3-70b-versatile", 
                groq_api_key=self.groq_key
            )

    def get_executor(self, db_manager_instance):
        
        # 1. Suntik Database menyang Tools
        set_global_db(db_manager_instance)

        llm = self._get_llm()

        # [FIX PENTING]: Ganti AgentType dadi OPENAI_FUNCTIONS. 
        # Iki ndhukung tool multi-input lan diakoni apik dening Groq/Gemini.
        agent = initialize_agent(
            tools=bot_tools, 
            llm=llm,
            agent=AgentType.OPENAI_FUNCTIONS, # <<< IKI KUNCINE
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            agent_kwargs={
                "system_message": """
                    Kamu adalah 'SpectrumBot', Customer Service andalan Spectrum Digital Printing.
                    Ikuti SOP PELAYANAN dengan ketat. (PHASE 1: cari_produk, PHASE 2: buat_pesanan).
                    Selalu jawab dengan luwes, tidak kaku, layaknya manusia. DILARANG KERAS mengarang Nomor Order (ORDER-xxxx).
                """
            }
        )
        # Catatan: Prompt lengkap sing dawa banget iku luwih apik diolah ing LLMService nek nggawe OPENAI_FUNCTIONS.
        
        return agent