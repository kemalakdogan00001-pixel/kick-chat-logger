import asyncio
import json
from playwright.async_api import async_playwright

# ROZET AYRIŞTIRICI: Özel kanal abonelik rozetlerini (Ay -> Resim URL) eşleştirir
def parse_kick_badges(identity, channel_sub_badges):
    parsed = []
    badges_list = identity.get("badges", [])
    
    for b in badges_list:
        b_type = str(b.get("type", "")).lower()
        b_text = str(b.get("text", ""))
        
        b_url = (
            b.get("url") or 
            b.get("path") or 
            b.get("image", {}).get("src") or 
            b.get("badge_image", {}).get("src") or 
            ""
        )
        
        css_class = ""
        
        if b_type == "broadcaster": 
            b_text = "Yayıncı"
            css_class = "kick-broadcaster"
        elif b_type == "moderator": 
            b_text = "Moderatör"
            css_class = "kick-mod"
        elif b_type == "vip": 
            b_text = "VIP"
            css_class = "kick-vip"
        elif b_type == "subscriber": 
            b_text = f"{b.get('count', 1)} Ay Abone"
            css_class = "kick-sub"
            
            b_count = b.get("count", 1)
            
            if b_count in channel_sub_badges:
                b_url = channel_sub_badges[b_count]
            else:
                available_months = sorted(channel_sub_badges.keys())
                if available_months:
                    selected_month = available_months[0]
                    for m in available_months:
                        if m <= b_count:
                            selected_month = m
                    b_url = channel_sub_badges[selected_month]
                elif 1 in channel_sub_badges:
                    b_url = channel_sub_badges[1]
                    
        elif b_type == "founder": 
            b_text = "Kurucu"
            css_class = "kick-founder"
        elif b_type == "og": 
            b_text = "OG"
            css_class = "kick-og"
        elif b_type == "verified": 
            b_text = "Onaylı"
            css_class = "kick-verified"
        elif b_type == "bot":
            b_text = "Bot"
            css_class = "kick-bot"

        if b_type == "subscriber" and b_url:
            b_text = ""

        parsed.append({
            "url": b_url, 
            "name": b_text, 
            "css_class": css_class
        })
    return parsed


async def start_kick_bot(username: str, message_callback):
    channel_sub_badges = {}

    async def handle_ws_frame(payload):
        if isinstance(payload, bytes):
            text = payload.decode('utf-8', errors='ignore')
        else:
            text = str(payload)
            
        if not text:
            return
            
        try:
            packet = json.loads(text)
            
            if "push" in packet and "pub" in packet["push"]:
                pub_data = packet["push"]["pub"].get("data", {})
                
                if isinstance(pub_data, str):
                    pub_data = json.loads(pub_data)
                    
                event_name = pub_data.get("event", "")
                
                if "ChatMessage" in event_name:
                    raw_data = pub_data.get("data", {})
                    
                    if isinstance(raw_data, str):
                        raw_data = json.loads(raw_data)
                        
                    sender = raw_data.get("sender", {})
                    username_val = sender.get("username", "Bilinmeyen")
                    content = raw_data.get("content", "")
                    
                    if not content:
                        return

                    badges = parse_kick_badges(sender.get("identity", {}), channel_sub_badges)
                    avatar = sender.get("profile_pic") or f"https://ui-avatars.com/api/?name={username_val}&background=27272a&color=fff"

                    kick_data = {
                        "platform": "kick",
                        "type": "chat",
                        "avatar": avatar,
                        "username": username_val,
                        "badges": badges,
                        "message": content
                    }
                    asyncio.create_task(message_callback(kick_data))
                    
                elif event_name and "App\\Events" in event_name and "ChatMessage" not in event_name:
                    raw_data = pub_data.get("data", {})
                    
                    if isinstance(raw_data, str):
                        try:
                            raw_data = json.loads(raw_data)
                        except Exception:
                            pass
                    
                    event_short = event_name.split("\\")[-1]
                    
                    username_val = "Bilinmeyen"
                    if isinstance(raw_data, dict):
                        if "gifter_username" in raw_data:
                            username_val = raw_data["gifter_username"]
                        elif "username" in raw_data:
                            username_val = raw_data["username"]
                        elif "user" in raw_data and isinstance(raw_data["user"], dict):
                            username_val = raw_data["user"].get("username", "Bilinmeyen")
                        elif "sender" in raw_data and isinstance(raw_data["sender"], dict):
                            username_val = raw_data["sender"].get("username", "Bilinmeyen")
                            
                    avatar = f"https://ui-avatars.com/api/?name={username_val}&background=27272a&color=fff"
                    
                    if "Subscription" in event_short or "Gift" in event_short:
                        gift_name = "Abonelik Hediye Etti" if "Gift" in event_short else "Abone Oldu"
                        gift_count = raw_data.get("gifted_subscriptions_count", 1) if "Gift" in event_short else raw_data.get("months", 1)
                        
                        kick_data = {
                            "platform": "kick",
                            "type": "gift",
                            "avatar": avatar,
                            "username": username_val,
                            "badges": [],
                            "message": f"Kanalına {gift_name}!",
                            "gift_id": event_short,
                            "gift_name": gift_name,
                            "gift_count": gift_count,
                            "total_coins": 0,
                            "gift_icon": ""
                        }
                        asyncio.create_task(message_callback(kick_data))
                        
                    elif "Follow" in event_short or "Host" in event_short:
                        action = "seni takip etmeye başladı! 🎉" if "Follow" in event_short else "seni hostladı! 🚀"
                        
                        kick_data = {
                            "platform": "kick",
                            "type": "chat",
                            "avatar": avatar,
                            "username": username_val,
                            "badges": [{"name": "BİLDİRİM", "url": "", "css_class": ""}],
                            "message": f"<b>{action}</b>"
                        }
                        asyncio.create_task(message_callback(kick_data))
                    
        except Exception:
            pass

    async def handle_response(response):
        if f"api/v2/channels/{username}/messages" in response.url:
            try:
                data = await response.json()
                messages = data.get("data", {}).get("messages", [])
                if messages:
                    messages.reverse() 
                    for msg in messages:
                        sender = msg.get("sender", {})
                        username_val = sender.get("username", "Bilinmeyen")
                        content = msg.get("content", "")
                        if not content:
                            continue
                        
                        badges = parse_kick_badges(sender.get("identity", {}), channel_sub_badges)
                        avatar = sender.get("profile_pic") or f"https://ui-avatars.com/api/?name={username_val}&background=27272a&color=fff"
                        
                        kick_data = {
                            "platform": "kick",
                            "type": "chat",
                            "avatar": avatar,
                            "username": username_val,
                            "badges": badges,
                            "message": content
                        }
                        asyncio.create_task(message_callback(kick_data))
            except Exception:
                pass

    async def on_websocket(ws):
        if "kick.com" in ws.url:
            ws.on("framereceived", handle_ws_frame)

    while True:
        print(f"[Kick] '{username}' için Playwright Ağ Dinleyicisi başlatılıyor...")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--hide-scrollbars",
                        "--mute-audio",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu"
                    ],
                    ignore_default_args=["--enable-automation"]
                )
                
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )
                page = await context.new_page()
                
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
                """)
                
                page.on("response", handle_response)
                page.on("websocket", on_websocket)
                
                await page.goto(f"https://kick.com/popout/{username}/chat", wait_until="networkidle", timeout=60000)
                
                try:
                    sub_badges_data = await page.evaluate('''async (user) => {
                        try {
                            const res = await fetch(`https://kick.com/api/v1/channels/${user}`);
                            const data = await res.json();
                            return data.subscriber_badges || [];
                        } catch(e) {
                            return [];
                        }
                    }''', username)
                    
                    for badge in sub_badges_data:
                        months = badge.get("months", 1)
                        img_url = badge.get("badge_image", {}).get("src", "")
                        if img_url:
                            channel_sub_badges[months] = img_url
                            
                    if channel_sub_badges:
                        print(f"[Kick] Kanala özel {len(channel_sub_badges)} adet abonelik rozeti (SVG/PNG) başarıyla yüklendi!")
                except Exception as e:
                    print(f"[Kick] Abone rozetleri çekilirken hata: {e}")

                while True:
                    await asyncio.sleep(1)

        except Exception as e:
            print(f"[Kick] Bağlantı koptu veya hata oluştu ({e}). 15 saniye sonra yeniden başlatılıyor...")
            await asyncio.sleep(15)