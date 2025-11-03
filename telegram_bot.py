#!/usr/bin/env python3
"""
Telegram Bot for REO Dashboard Notifications
Handles user subscriptions and manages the subscriber database.
"""

import json
import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUBSCRIBERS_FILE = 'subscribers_telegram.json'
DASHBOARD_URL = 'https://dashboards.thegraph.foundation/reo/'
LOG_DIR = 'logs'
BOT_LOG_FILE = os.path.join(LOG_DIR, 'telegram_bot.log')
ACTIVITY_LOG_FILE = os.path.join(LOG_DIR, 'telegram_bot_activity.log')

# Create logs directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

# Set up logging with both console and file output
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(BOT_LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set up activity logger for tracking subscriber actions
activity_logger = logging.getLogger('activity')
activity_logger.setLevel(logging.INFO)
activity_handler = logging.FileHandler(ACTIVITY_LOG_FILE)
activity_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
activity_logger.addHandler(activity_handler)


def load_subscribers():
    """Load subscribers from JSON file."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        return {
            "subscribers": [],
            "stats": {
                "total_subscribers": 0,
                "total_notifications_sent": 0
            }
        }
    
    try:
        with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading subscribers: {e}")
        return {
            "subscribers": [],
            "stats": {
                "total_subscribers": 0,
                "total_notifications_sent": 0
            }
        }


def save_subscribers(data):
    """Save subscribers to JSON file."""
    try:
        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving subscribers: {e}")
        return False


def is_subscribed(chat_id):
    """Check if a chat_id is already subscribed."""
    data = load_subscribers()
    for sub in data.get("subscribers", []):
        if sub.get("chat_id") == chat_id and sub.get("active", False):
            return True
    return False


def add_subscriber(chat_id, username):
    """Add a new subscriber."""
    data = load_subscribers()
    
    # Check if already subscribed
    for sub in data.get("subscribers", []):
        if sub.get("chat_id") == chat_id:
            if sub.get("active", False):
                return False  # Already active
            else:
                # Reactivate
                sub["active"] = True
                sub["resubscribed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                data["stats"]["total_subscribers"] = sum(1 for s in data["subscribers"] if s.get("active", False))
                save_subscribers(data)
                return True
    
    # Add new subscriber
    subscriber = {
        "chat_id": chat_id,
        "username": username or "Unknown",
        "subscribed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "active": True,
        "watched_indexers": []  # Empty array means "watch all"
    }
    data["subscribers"].append(subscriber)
    data["stats"]["total_subscribers"] = sum(1 for s in data["subscribers"] if s.get("active", False))
    
    save_subscribers(data)
    return True


def remove_subscriber(chat_id):
    """Remove a subscriber (set to inactive and clear watched indexers)."""
    data = load_subscribers()
    
    for sub in data.get("subscribers", []):
        if sub.get("chat_id") == chat_id and sub.get("active", False):
            sub["active"] = False
            sub["unsubscribed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            # Clear watched indexers list when unsubscribing
            sub["watched_indexers"] = []
            data["stats"]["total_subscribers"] = sum(1 for s in data["subscribers"] if s.get("active", False))
            save_subscribers(data)
            return True
    
    return False


def add_watched_indexer(chat_id, indexer_address):
    """Add an indexer to a subscriber's watch list."""
    data = load_subscribers()
    
    # Normalize address to lowercase
    indexer_address = indexer_address.lower()
    
    for sub in data.get("subscribers", []):
        if sub.get("chat_id") == chat_id and sub.get("active", False):
            # Initialize watched_indexers if it doesn't exist
            if "watched_indexers" not in sub:
                sub["watched_indexers"] = []
            
            # Check if already watching
            if indexer_address in sub["watched_indexers"]:
                return {"success": False, "reason": "already_watching"}
            
            # Add to watch list
            sub["watched_indexers"].append(indexer_address)
            save_subscribers(data)
            return {"success": True, "count": len(sub["watched_indexers"])}
    
    return {"success": False, "reason": "not_subscribed"}


def remove_watched_indexer(chat_id, indexer_address):
    """Remove an indexer from a subscriber's watch list."""
    data = load_subscribers()
    
    # Normalize address to lowercase
    indexer_address = indexer_address.lower()
    
    for sub in data.get("subscribers", []):
        if sub.get("chat_id") == chat_id and sub.get("active", False):
            # Initialize watched_indexers if it doesn't exist
            if "watched_indexers" not in sub:
                sub["watched_indexers"] = []
            
            # Check if watching
            if indexer_address not in sub["watched_indexers"]:
                return {"success": False, "reason": "not_watching"}
            
            # Remove from watch list
            sub["watched_indexers"].remove(indexer_address)
            save_subscribers(data)
            return {"success": True, "count": len(sub["watched_indexers"])}
    
    return {"success": False, "reason": "not_subscribed"}


def get_watched_indexers(chat_id):
    """Get list of watched indexers for a subscriber."""
    data = load_subscribers()
    
    for sub in data.get("subscribers", []):
        if sub.get("chat_id") == chat_id and sub.get("active", False):
            return sub.get("watched_indexers", [])
    
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name or "User"
    
    # Log the /start command
    activity_logger.info(f"START - Chat ID: {chat_id}, Username: @{username}, Name: {first_name}")
    logger.info(f"/start command from {chat_id} (@{username})")
    
    welcome_message = f"""
🔔 **Welcome to REO Dashboard Notifications!**

This bot sends you real-time alerts about:
• Oracle updates
• Indexer status changes
• Grace period expirations

📊 View the dashboard: {DASHBOARD_URL}

**Available Commands:**
/subscribe - Subscribe to all notifications
/unsubscribe - Stop receiving all notifications
/watch <address> - Watch a specific indexer
/unwatch <address> - Stop watching an indexer
/watchlist - Show your watched indexers
/status - Check your subscription status
/stats - View bot statistics
/help - Show this help message

💡 **Tip:** Use /subscribe to get started!
"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name or "User"
    last_name = update.effective_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    logger.info(f"/subscribe command from {chat_id} (@{username})")
    
    if is_subscribed(chat_id):
        activity_logger.info(f"SUBSCRIBE_ATTEMPT (Already subscribed) - Chat ID: {chat_id}, Username: @{username}, Name: {full_name}")
        await update.message.reply_text(
            "✅ You're already subscribed to notifications!\n\n"
            f"📊 View dashboard: {DASHBOARD_URL}\n"
            "Use /unsubscribe to stop receiving alerts."
        )
        return
    
    if add_subscriber(chat_id, username):
        activity_logger.info(f"NEW_SUBSCRIBER ✅ - Chat ID: {chat_id}, Username: @{username}, Name: {full_name}")
        logger.info(f"New subscriber: {chat_id} (@{username})")
        await update.message.reply_text(
            "🎉 **Successfully subscribed!**\n\n"
            "You will now receive notifications about:\n"
            "• Oracle updates\n"
            "• Indexer status changes\n"
            "• Grace period expirations\n\n"
            f"📊 Dashboard: {DASHBOARD_URL}\n\n"
            "Use /unsubscribe anytime to stop receiving alerts.",
            parse_mode='Markdown'
        )
    else:
        activity_logger.info(f"SUBSCRIBE_FAILED ❌ - Chat ID: {chat_id}, Username: @{username}")
        logger.error(f"Failed to subscribe: {chat_id} (@{username})")
        await update.message.reply_text(
            "❌ Failed to subscribe. Please try again later."
        )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe command."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name or "User"
    last_name = update.effective_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    logger.info(f"/unsubscribe command from {chat_id} (@{username})")
    
    if not is_subscribed(chat_id):
        activity_logger.info(f"UNSUBSCRIBE_ATTEMPT (Not subscribed) - Chat ID: {chat_id}, Username: @{username}")
        await update.message.reply_text(
            "ℹ️ You're not currently subscribed.\n\n"
            "Use /subscribe to start receiving notifications."
        )
        return
    
    if remove_subscriber(chat_id):
        activity_logger.info(f"UNSUBSCRIBED 👋 - Chat ID: {chat_id}, Username: @{username}, Name: {full_name}")
        logger.info(f"Unsubscribed: {chat_id} (@{username})")
        await update.message.reply_text(
            "👋 *Successfully unsubscribed!*\n\n"
            "You will no longer receive any notifications.\n"
            "Your watch list has been cleared.\n\n"
            "You can subscribe again anytime using /subscribe.",
            parse_mode='Markdown'
        )
    else:
        activity_logger.info(f"UNSUBSCRIBE_FAILED ❌ - Chat ID: {chat_id}, Username: @{username}")
        logger.error(f"Failed to unsubscribe: {chat_id} (@{username})")
        await update.message.reply_text(
            "❌ Failed to unsubscribe. Please try again later."
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    logger.info(f"/status command from {chat_id} (@{username})")
    
    if is_subscribed(chat_id):
        data = load_subscribers()
        for sub in data.get("subscribers", []):
            if sub.get("chat_id") == chat_id:
                subscribed_at = sub.get("subscribed_at", "Unknown")
                activity_logger.info(f"STATUS_CHECK (Subscribed) - Chat ID: {chat_id}, Username: @{username}, Since: {subscribed_at}")
                await update.message.reply_text(
                    f"✅ *Subscription Status: Active*\n\n"
                    f"👤 Username: @{username or 'Unknown'}\n"
                    f"📅 Subscribed: {subscribed_at}\n"
                    f"🔔 Receiving: Oracle & Status updates\n\n"
                    f"📊 Dashboard: {DASHBOARD_URL}",
                    parse_mode='Markdown'
                )
                return
    else:
        activity_logger.info(f"STATUS_CHECK (Not subscribed) - Chat ID: {chat_id}, Username: @{username}")
        await update.message.reply_text(
            "❌ *Subscription Status: Not Active*\n\n"
            "Use /subscribe to start receiving notifications.",
            parse_mode='Markdown'
        )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    logger.info(f"/stats command from {chat_id} (@{username})")
    
    data = load_subscribers()
    total_subs = data.get("stats", {}).get("total_subscribers", 0)
    total_notifs = data.get("stats", {}).get("total_notifications_sent", 0)
    
    activity_logger.info(f"STATS_VIEW - Chat ID: {chat_id}, Username: @{username}")
    
    await update.message.reply_text(
        f"📊 **Bot Statistics**\n\n"
        f"👥 Active Subscribers: {total_subs}\n"
        f"📤 Notifications Sent: {total_notifs}\n\n"
        f"🌐 Dashboard: {DASHBOARD_URL}",
        parse_mode='Markdown'
    )


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /watch command - watch a specific indexer."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    logger.info(f"/watch command from {chat_id} (@{username})")
    
    if not is_subscribed(chat_id):
        await update.message.reply_text(
            "❌ You must be subscribed first.\n\n"
            "Use /subscribe to get started."
        )
        return
    
    # Check if address provided
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ **Usage:** /watch <indexer_address>\n\n"
            "**Example:**\n"
            "`/watch 0x1234...5678`\n\n"
            "You can watch specific indexers to receive notifications only about them.\n"
            "Leave your watch list empty to receive all notifications.",
            parse_mode='Markdown'
        )
        return
    
    indexer_address = context.args[0].strip()
    
    # Basic validation
    if not indexer_address.startswith('0x') or len(indexer_address) != 42:
        await update.message.reply_text(
            "❌ Invalid Ethereum address format.\n\n"
            "Address should start with 0x and be 42 characters long.\n"
            "**Example:** `0x1234567890abcdef1234567890abcdef12345678`",
            parse_mode='Markdown'
        )
        return
    
    result = add_watched_indexer(chat_id, indexer_address)
    
    if result["success"]:
        activity_logger.info(f"WATCH_ADD ✅ - Chat ID: {chat_id}, Username: @{username}, Indexer: {indexer_address}")
        await update.message.reply_text(
            f"✅ *Now watching indexer:*\n"
            f"`{indexer_address}`\n\n"
            f"👀 Total watched: {result['count']}\n\n"
            f"You'll receive notifications only for watched indexers.\n"
            f"Use /watchlist to see all watched indexers.",
            parse_mode='Markdown'
        )
    elif result["reason"] == "already_watching":
        await update.message.reply_text(
            f"ℹ️ You're already watching this indexer:\n"
            f"`{indexer_address}`\n\n"
            f"Use /watchlist to see all watched indexers.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ Failed to add indexer to watch list. Please try again."
        )


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unwatch command - stop watching a specific indexer."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    logger.info(f"/unwatch command from {chat_id} (@{username})")
    
    if not is_subscribed(chat_id):
        await update.message.reply_text(
            "❌ You must be subscribed first.\n\n"
            "Use /subscribe to get started."
        )
        return
    
    # Check if address provided
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ **Usage:** /unwatch <indexer_address>\n\n"
            "**Example:**\n"
            "`/unwatch 0x1234...5678`\n\n"
            "Use /watchlist to see all watched indexers.",
            parse_mode='Markdown'
        )
        return
    
    indexer_address = context.args[0].strip()
    
    result = remove_watched_indexer(chat_id, indexer_address)
    
    if result["success"]:
        activity_logger.info(f"WATCH_REMOVE ✅ - Chat ID: {chat_id}, Username: @{username}, Indexer: {indexer_address}")
        
        if result["count"] == 0:
            await update.message.reply_text(
                f"✅ *Stopped watching:*\n"
                f"`{indexer_address}`\n\n"
                f"📢 Watch list is now empty.\n"
                f"You'll receive notifications for *all indexers*.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"✅ *Stopped watching:*\n"
                f"`{indexer_address}`\n\n"
                f"👀 Total watched: {result['count']}\n\n"
                f"Use /watchlist to see remaining watched indexers.",
                parse_mode='Markdown'
            )
    elif result["reason"] == "not_watching":
        await update.message.reply_text(
            f"ℹ️ You're not watching this indexer:\n"
            f"`{indexer_address}`\n\n"
            f"Use /watchlist to see watched indexers.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ Failed to remove indexer from watch list. Please try again."
        )


async def watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /watchlist command - show list of watched indexers."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    logger.info(f"/watchlist command from {chat_id} (@{username})")
    
    if not is_subscribed(chat_id):
        await update.message.reply_text(
            "❌ You must be subscribed first.\n\n"
            "Use /subscribe to get started."
        )
        return
    
    watched = get_watched_indexers(chat_id)
    
    if watched is None:
        await update.message.reply_text(
            "❌ Could not retrieve watch list. Please try again."
        )
        return
    
    if len(watched) == 0:
        await update.message.reply_text(
            "📢 *Watching: All Indexers*\n\n"
            "You're currently receiving notifications for all indexers.\n\n"
            "💡 *Tip:* Use `/watch <address>` to watch specific indexers only.\n\n"
            f"📊 Dashboard: {DASHBOARD_URL}",
            parse_mode='Markdown'
        )
    else:
        indexer_list = "\n".join([f"• `{addr}`" for addr in watched])
        await update.message.reply_text(
            f"👀 *Watched Indexers ({len(watched)}):*\n\n"
            f"{indexer_list}\n\n"
            f"You'll receive notifications only for these indexers.\n\n"
            f"💡 Use `/unwatch <address>` to remove an indexer.\n"
            f"📊 Dashboard: {DASHBOARD_URL}",
            parse_mode='Markdown'
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    logger.info(f"/help command from {chat_id} (@{username})")
    activity_logger.info(f"HELP_VIEW - Chat ID: {chat_id}, Username: @{username}")
    
    help_text = f"""
📖 *REO Dashboard Bot - Help*

*Available Commands:*

/start - Welcome message and introduction
/subscribe - Subscribe to all notifications
/unsubscribe - Stop receiving all notifications
/watch <address> - Watch a specific indexer
/unwatch <address> - Stop watching an indexer
/watchlist - Show your watched indexers
/status - Check your subscription status
/stats - View bot statistics
/help - Show this help message

*What You'll Receive:*

🔔 *Oracle Updates* - When the eligibility oracle runs
📝 *Status Changes* - When indexers change status
⚠️ *Grace Periods* - When indexers enter/exit grace period
❌ *Ineligibility* - When indexers become ineligible

*Watch Specific Indexers:*

By default, you receive notifications for all indexers.
Use `/watch` to monitor only specific indexers you care about.

*Dashboard:*
{DASHBOARD_URL}

*About GIP-0079:*
This bot monitors the Indexer Rewards Eligibility Oracle that tracks which indexers are eligible for rewards based on their service quality:
https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /test command - sends a test notification."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    logger.info(f"/test command from {chat_id} (@{username})")
    
    if not is_subscribed(chat_id):
        activity_logger.info(f"TEST_FAILED (Not subscribed) - Chat ID: {chat_id}, Username: @{username}")
        await update.message.reply_text(
            "❌ You must be subscribed to test notifications.\n\n"
            "Use /subscribe first."
        )
        return
    
    test_message = f"""
🧪 **Test Notification**

This is a test message to confirm notifications are working correctly.

If you received this, you're all set! ✅

📊 Dashboard: {DASHBOARD_URL}
"""
    
    activity_logger.info(f"TEST_NOTIFICATION_SENT 🧪 - Chat ID: {chat_id}, Username: @{username}")
    await update.message.reply_text(test_message, parse_mode='Markdown')
    logger.info(f"Test notification sent to: {chat_id} (@{username})")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        print("❌ Error: TELEGRAM_BOT_TOKEN not set in .env file")
        return
    
    # Log bot startup
    startup_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    activity_logger.info(f"========== BOT STARTED ==========")
    activity_logger.info(f"Startup Time: {startup_time}")
    
    # Load initial subscriber count
    data = load_subscribers()
    total_subs = data.get("stats", {}).get("total_subscribers", 0)
    activity_logger.info(f"Active Subscribers: {total_subs}")
    activity_logger.info(f"=================================")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("unwatch", unwatch))
    application.add_handler(CommandHandler("watchlist", watchlist))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting REO Dashboard Telegram Bot...")
    print("✅ REO Dashboard Telegram Bot is running!")
    print("📱 Users can now subscribe by sending /start")
    print(f"📊 Current subscribers: {total_subs}")
    print("🛑 Press Ctrl+C to stop the bot")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

