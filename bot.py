import asyncio
import nest_asyncio
import traceback
import urllib.parse  # <<< WAJIB: Kanggo encode link WA
from telegram import Update, BotCommand  # <<< TAMBAH: BotCommand kanggo Menu
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
        """Mbusak memori chat user."""
        chat_id = update.effective_chat.id
        self.user_sessions[chat_id] = []
        await update.message.reply_text("🧠 Memori Reset. SpectrumBot siap mulai dari awal, Kak!")

    async def _chat_admin_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ngekei link langsung menyang WhatsApp Admin."""
        chat_id = update.effective_chat.id
        wa_admin = "6281234567890" # <<< GANTI KARO NOMER WA ADMINE
        pesan_otomatis = "Halo Admin Spectrum, saya butuh bantuan manual."
        
        # Encode pesan dadi format URL
        link_wa = f"https://wa.me/{wa_admin}?text={urllib.parse.quote(pesan_otomatis)}"
        
        teks_balasan = (
            "Siap Kak! 🫡\n\n"
            "Jika ada kendala khusus atau butuh negosiasi harga partai besar, "
            "Kakak bisa langsung chat Admin manusia kami di sini:\n\n"
            f"👉 [Hubungi Admin via WhatsApp]({link_wa})\n\n"
            "Kami siap melayani Kakak!"
        )
        await update.message.reply_text(teks_balasan, parse_mode="Markdown")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        chat_id = update.effective_chat.id
        
        if chat_id not in self.user_sessions: 
            self.user_sessions[chat_id] = []
        
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Jupuk Executor (Agent)
        agent = self.llm_service.get_executor(self.db_manager) 
        
        # History Management
        history = self.user_sessions[chat_id]
        if len(history) > 10:
            history = history[-10:]
        
        try:
            response = await agent.ainvoke({"input": text, "chat_history": history})
            reply = response.get("output", "Maaf Kak, aku bingung mau jawab apa. Bisa diulangi?")
            
            # Simpen menyang memori
            self.user_sessions[chat_id].append(HumanMessage(content=text))
            self.user_sessions[chat_id].append(AIMessage(content=reply))
            
            await update.message.reply_text(reply)
            
        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()
            await update.message.reply_text("⚠️ Maaf Kak, sistem lagi ada gangguan teknis. Coba lagi ya!")

    async def run(self):
        app = ApplicationBuilder().token(self.token).build()
        
        # Register Commands
        app.add_handler(CommandHandler("reset", self._reset_handler))
        app.add_handler(CommandHandler("chatadmin", self._chat_admin_handler))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
        
        # Set Menu Button otomatis nang Telegram
        await app.initialize()
        await app.bot.set_my_commands([
            BotCommand("reset", "Mulai ulang percakapan"),
            BotCommand("chatadmin", "Hubungi Admin Manusia (WA)")
        ])
        
        nest_asyncio.apply()
        print("🚀 SpectrumBot Is Online & Menu Commands Ready...")
        
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        
        # Njaga bot tetep urip
        stop_event = asyncio.Event()
        await stop_event.wait()

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN")
    
    try:
        # Pass secrets/env sesuai kebutuhan DatabaseManager
        db_instance = DatabaseManager(os_getenv_func=os.environ.get)
        llm_service = LLMService("Groq Llama 3") 
        bot = TelegramBot(token, llm_service, db_instance)
        
        asyncio.run(bot.run())
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")