#!/usr/bin/env python3
"""
Announcement Script - Send update notifications to existing subscribers
This script sends a one-time announcement about new features to all active subscribers.
"""

import json
import os
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUBSCRIBERS_FILE = 'subscribers_telegram.json'
DASHBOARD_URL = 'http://dashboards.thegraph.foundation/reo/'

# Announcement message
ANNOUNCEMENT_MESSAGE = """
**🎉 New Features Available!**

Great news! The REO Dashboard bot now supports **indexer-specific subscriptions**!

**What's New:**

🎯 **Watch Specific Indexers**
You can now choose to receive notifications only for indexers you care about:

• `/watch <address>` - Watch a specific indexer
• `/unwatch <address>` - Stop watching an indexer
• `/watchlist` - View your watched indexers

**How It Works:**

✅ By default, you receive notifications for **all indexers** (current behavior)
✅ Add indexers to your watch list to receive **only their updates**
✅ Watch multiple indexers - it's up to you!
✅ Empty watch list = all notifications (default)

**Example:**
```
/watch 0x1234567890abcdef1234567890abcdef12345678
```

📖 Type `/help` to see all available commands!

📊 Dashboard: {url}
""".format(url=DASHBOARD_URL)


def load_subscribers():
    """Load active subscribers from JSON file."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        print(f"❌ Subscribers file not found: {SUBSCRIBERS_FILE}")
        return []
    
    try:
        with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Return only active subscribers
            active = [sub for sub in data.get("subscribers", []) if sub.get("active", False)]
            print(f"✅ Loaded {len(active)} active subscriber(s)")
            return active
    except Exception as e:
        print(f"❌ Error loading subscribers: {e}")
        return []


async def send_announcement_to_subscriber(bot, chat_id, username):
    """Send announcement to a single subscriber."""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=ANNOUNCEMENT_MESSAGE,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        print(f"  ✅ Sent to {chat_id} (@{username})")
        return True
    except TelegramError as e:
        print(f"  ❌ Failed to send to {chat_id} (@{username}): {e}")
        return False


async def send_announcements_async():
    """Send announcements to all active subscribers."""
    # Check if bot token is set
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
        print("   Please set it in your .env file")
        return False
    
    # Load subscribers
    subscribers = load_subscribers()
    if not subscribers:
        print("❌ No active subscribers found")
        return False
    
    print(f"\n📢 Sending announcements to {len(subscribers)} subscriber(s)...\n")
    
    # Create bot instance
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Send announcements
    success_count = 0
    fail_count = 0
    
    for subscriber in subscribers:
        chat_id = subscriber.get("chat_id")
        username = subscriber.get("username", "Unknown")
        
        if not chat_id:
            continue
        
        try:
            if await send_announcement_to_subscriber(bot, chat_id, username):
                success_count += 1
            else:
                fail_count += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"  ❌ Error sending to {chat_id}: {e}")
            fail_count += 1
    
    print(f"\n{'='*60}")
    print(f"📊 Results:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Failed: {fail_count}")
    print(f"   📈 Total: {len(subscribers)}")
    print(f"{'='*60}\n")
    
    return success_count > 0


def send_announcements():
    """Send announcements (wrapper function)."""
    try:
        return asyncio.run(send_announcements_async())
    except Exception as e:
        print(f"❌ Error in send_announcements: {e}")
        return False


if __name__ == '__main__':
    print("="*60)
    print("📢 REO Dashboard Bot - Update Announcement")
    print("="*60)
    print("\nThis will send an announcement about new features to all")
    print("active subscribers.\n")
    
    # Ask for confirmation
    response = input("Do you want to continue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        print("\n🚀 Sending announcements...\n")
        success = send_announcements()
        
        if success:
            print("✅ Announcements sent successfully!")
        else:
            print("⚠️  Some or all announcements failed. Check the output above.")
    else:
        print("\n❌ Announcement cancelled.")

