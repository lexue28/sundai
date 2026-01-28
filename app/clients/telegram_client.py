import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters, ContextTypes

load_dotenv()


class TelegramClient:
    """Client for sending posts to Telegram for human approval."""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID not found in environment variables")
        
        # State for feedback flow
        self.feedback_pending_post = None
        self.feedback_decision = None
        self.feedback_reason = None
        self.waiting_for_reason = False
        self.feedback_done = asyncio.Event()
        self.app = None
    
    async def wait_for_approval_with_feedback(self, post_content: str) -> tuple[str, str | None]:
        """
        Send post for approval. If rejected, collect the reason.
        Returns (decision, rejection_reason).
        decision is either "approve" or "reject"
        """
        # Reset state
        self.feedback_pending_post = post_content
        self.feedback_decision = None
        self.feedback_reason = None
        self.waiting_for_reason = False
        self.feedback_done.clear()
        
        # Create handlers
        async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()
            
            if query.data == "approve":
                self.feedback_decision = "approve"
                await query.edit_message_text(f"✅ APPROVED\n\n{self.feedback_pending_post}")
                self.feedback_done.set()
            elif query.data == "reject":
                self.feedback_decision = "reject"
                self.waiting_for_reason = True
                await query.edit_message_text(
                    "❌ REJECTED\n\n"
                    "Please reply with the reason for rejection.\n"
                    "This feedback helps improve future posts.\n\n"
                    "Examples: 'Too promotional' or 'Wrong tone'"
                )
        
        async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not self.waiting_for_reason:
                return
            
            self.feedback_reason = update.message.text
            self.waiting_for_reason = False
            await update.message.reply_text(
                f"📝 Feedback recorded!\n\nReason: {self.feedback_reason}"
            )
            self.feedback_done.set()
        
        # Send the post with approval buttons
        bot = Bot(token=self.bot_token)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data="approve"),
                InlineKeyboardButton("❌ Reject", callback_data="reject"),
            ]
        ])
        
        await bot.send_message(
            chat_id=int(self.chat_id),
            text=f"📝 New Post for Approval\n\n{post_content}\n\nCharacters: {len(post_content)}",
            reply_markup=keyboard,
        )
        
        # Set up listeners
        self.app = Application.builder().token(self.bot_token).build()
        self.app.add_handler(CallbackQueryHandler(handle_button))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        # Wait for completion
        await self.feedback_done.wait()
        
        # Cleanup
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        
        return self.feedback_decision, self.feedback_reason
