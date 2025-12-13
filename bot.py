import asyncio
import nest_asyncio
import traceback
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from langchain_core.messages import AIMessage, HumanMessage
from llm_service import LLMService

class TelegramBot:
    """Mengelola Lifecycle Bot Telegram."""
    
    def __init__(self, token, llm_service: LLMService):
        self.token = token
        self.llm_service = llm_service
        self.user_sessions = {}

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        chat_id = update.effective_chat.id
        
        print(f"📩 Pesan dari {chat_id}: {text}")
        
        if chat_id not in self.user_sessions: self.user_sessions[chat_id] = []
        if text == "/reset":
            self.user_sessions[chat_id] = []
            await update.message.reply_text("🧠 Memori Reset.")
            return

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Init Agent
        agent = self.llm_service.get_executor()
        history = self.user_sessions[chat_id]
        history.append(HumanMessage(content=text))
        
        try:
            response = await agent.ainvoke({"input": text, "chat_history": history})
            reply = response["output"] or "Maaf, respon kosong."
            
            history.append(AIMessage(content=reply))
            await update.message.reply_text(reply)
            print(f"📤 Balasan: {reply}")
            
        except Exception as e:
            err_msg = f"Error: {e}"
            print(err_msg)
            traceback.print_exc()
            await update.message.reply_text("⚠️ Ada gangguan sistem. Silakan coba lagi.")

    async def run(self):
        """Menjalankan Polling."""
        app = ApplicationBuilder().token(self.token).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
        nest_asyncio.apply()
        
        print("🔄 Inisialisasi Bot...")
        await app.initialize()
        await app.start()
        print("🚀 Bot Polling Started...")
        await app.updater.start_polling(drop_pending_updates=True)
        
        while True: await asyncio.sleep(3600)