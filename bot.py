import asyncio
import nest_asyncio
import traceback
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from langchain_core.messages import AIMessage, HumanMessage
from llm_service import LLMService
from database import DatabaseManager 

class TelegramBot:
    def __init__(self, token, llm_service: LLMService, db_manager: DatabaseManager): 
        self.token = token
        self.llm_service = llm_service
        self.db_manager = db_manager
        self.user_sessions = {}

    async def _reset_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fungsi khusus nggo nanganin /reset"""
        chat_id = update.effective_chat.id
        self.user_sessions[chat_id] = []
        await update.message.reply_text("🧠 Memori Reset. SpectrumBot siap mulai dari awal, Kak!")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        chat_id = update.effective_chat.id
        
        # 1. Inisialisasi session nek durung onok
        if chat_id not in self.user_sessions: 
            self.user_sessions[chat_id] = []
        
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # 2. Jupuk executor (Agent)
        agent = self.llm_service.get_executor(self.db_manager) 
        
        # 3. Kelola History (Limit dadi 10 pesen terakhir)
        history = self.user_sessions[chat_id]
        if len(history) > 10:
            history = history[-10:] # Njaga supaya gak over-token
        
        try:
            # 4. Celuk AI
            response = await agent.ainvoke({"input": text, "chat_history": history})
            reply = response.get("output", "Waduh Kak, aku bingung mau jawab apa. Bisa diulangi?")
            
            # 5. Update Memory
            self.user_sessions[chat_id].append(HumanMessage(content=text))
            self.user_sessions[chat_id].append(AIMessage(content=reply))
            
            await update.message.reply_text(reply)
            
        except Exception as e:
            print(f"ERROR: {e}")
            await update.message.reply_text("⚠️ Maaf Kak, sistem Spectrum lagi sibuk sebentar. Coba lagi ya!")

    async def run(self):
        app = ApplicationBuilder().token(self.token).build()
        
        # Tambahno CommandHandler dhisik
        app.add_handler(CommandHandler("reset", self._reset_handler))
        # MessageHandler nampung teks biasa (dudu command)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
        
        # Iki cara sing luwih rapi nggo njaga bot tetep urip
        print("🚀 SpectrumBot Is Online...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        
        # Stop signal (njaga script gak langsung nutup)
        stop_event = asyncio.Event()
        await stop_event.wait()

        
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from llm_service import LLMService
    from database import DatabaseManager
    
    load_dotenv()
    
    print("🤖 Menyalakan SpectrumBot System...")
    
    token = os.getenv("TELEGRAM_TOKEN")
    
    try:
        db_instance = DatabaseManager()
    except Exception as e:
        print(f"❌ Gagal konek database: {e}")
        exit()
        
    # Inisialisasi Service
    llm_service = LLMService("Groq Llama 3") 
    bot = TelegramBot(token, llm_service, db_instance) # Kirim instance database!
    
    # Gas Pol!
    asyncio.run(bot.run())