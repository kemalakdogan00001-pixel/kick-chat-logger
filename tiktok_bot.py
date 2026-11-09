import asyncio
from collections import deque
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, CommentEvent, GiftEvent
from TikTokLive.client.web.web_settings import WebDefaults

async def start_tiktok_bot(username: str, message_callback):
    WebDefaults.tiktok_sign_api_key = "euler_YjI0Yzc5NGVhYjAyMmEwZmEwMWFlMmIxNDExMTIzOWYwOTk5MWFjODZlZTAzMTk0ODNkNmM4"

    # Son işlenen 500 mesajın ID'sini tutarak tekrarları engeller
    processed_message_ids = deque(maxlen=500)

    async def parse_and_send(user_obj, message_text, msg_type="chat", gift_data=None):
        profile_pic = ""
        badges = []
        seen_urls = set()

        def add_badge(url, name=""):
            identifier = url if url else name
            if identifier and identifier not in seen_urls:
                if url and "avatar" in str(url).lower():
                    return
                badges.append({
                    "url": str(url) if url else "",
                    "name": str(name).strip() if name else ""
                })
                seen_urls.add(identifier)

        try:
            if user_obj:
                avatar_obj = getattr(user_obj, 'avatar_thumb', None) or getattr(user_obj, 'profile_picture', None) or getattr(user_obj, 'avatar', None)
                if avatar_obj and hasattr(avatar_obj, 'url_list') and avatar_obj.url_list:
                    profile_pic = avatar_obj.url_list[0]
                elif avatar_obj and hasattr(avatar_obj, 'urls') and avatar_obj.urls:
                    profile_pic = avatar_obj.urls[0]

                badges_list = getattr(user_obj, 'badges', None)
                if badges_list:
                    for badge in badges_list:
                        b_url = ""
                        image_obj = getattr(badge, 'image', None)
                        if image_obj and hasattr(image_obj, 'url_list') and image_obj.url_list:
                             b_url = image_obj.url_list[0]
                        elif image_obj and hasattr(image_obj, 'urls') and image_obj.urls:
                             b_url = image_obj.urls[0]
                             
                        b_name = getattr(badge, 'name', "") or getattr(badge, 'display_name', "")
                        level = getattr(badge, 'level', None)
                        if level: b_name = f"Lv.{level}"
                        if b_url or b_name: add_badge(b_url, b_name)

                badge_list_raw = getattr(user_obj, 'badge_list', None)
                if badge_list_raw:
                    for badge in badge_list_raw:
                        image_attr = getattr(badge, 'image', None)
                        if image_attr:
                            inner = getattr(image_attr, 'image', None)
                            urls = getattr(inner, 'url_list', []) or getattr(inner, 'urls', []) if inner else getattr(image_attr, 'url_list', []) or getattr(image_attr, 'urls', [])
                            if urls: add_badge(urls[0])
                        
                        combine_attr = getattr(badge, 'combine', None)
                        if combine_attr:
                            icon = getattr(combine_attr, 'icon', None)
                            b_url = getattr(icon, 'url_list', [])[0] if icon and getattr(icon, 'url_list', []) else ""
                            if not b_url: b_url = getattr(icon, 'urls', [])[0] if icon and getattr(icon, 'urls', []) else ""
                            str_val = getattr(combine_attr, 'str', "")
                            if str_val or b_url: add_badge(b_url, str_val)

                badge_image_list = getattr(user_obj, 'badgeImageList', None) or getattr(user_obj, 'badge_image_list', None)
                if badge_image_list:
                     for badge_img in badge_image_list:
                         urls = getattr(badge_img, 'url_list', []) or getattr(badge_img, 'urls', [])
                         if urls: add_badge(urls[0])
        except Exception:
            pass

        username_str = getattr(user_obj, 'nickname', 'Bilinmeyen Kullanıcı') if user_obj else 'User'

        data = {
            "platform": "tiktok",
            "type": msg_type,
            "avatar": profile_pic,
            "username": username_str,
            "badges": badges,
            "message": message_text
        }
        
        if gift_data:
            data.update(gift_data)
        
        print(f"[TikTok {msg_type.upper()}] [{username_str}]: {message_text} | Coin: {gift_data.get('total_coins', 0) if gift_data else 0}")
        await message_callback(data)

    while True:
        client = TikTokLiveClient(unique_id=username)

        @client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            print(f"[TikTok] Bağlandı: @{client.unique_id} yayınındaki chati dinliyor...")

        @client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            # 1. Benzersiz kimlik kontrolü (event.id veya kullanıcı+yorum kombinasyonu)
            msg_id = getattr(event, 'id', None) or f"{getattr(event.user, 'user_id', '')}_{event.comment}"
            if msg_id in processed_message_ids:
                return
            processed_message_ids.append(msg_id)

            user_obj = getattr(event, 'user', None)
            message_text = getattr(event, 'comment', '')
            await parse_and_send(user_obj, message_text, msg_type="chat")

        @client.on(GiftEvent)
        async def on_gift(event: GiftEvent):
            gift_obj = getattr(event, 'gift', None)
            user_obj = getattr(event, 'user', None)
            
            if gift_obj:
                # TikTokLive hediyelerde kombo artarken sürekli event fırlatır,
                # combo_count 1'den büyükken yalnızca son halini veya streak bitişini almak isteyebilirsiniz.
                gift_name = getattr(gift_obj, 'name', getattr(gift_obj, 'describe', 'Hediye'))
                combo_count = getattr(gift_obj, 'combo', getattr(gift_obj, 'count', getattr(gift_obj, 'repeat_count', 1)))
                gift_id = getattr(gift_obj, 'id', getattr(gift_obj, 'gift_id', 0))
                
                diamond_count = 0
                gift_info = getattr(gift_obj, 'info', None)
                if gift_info:
                    diamond_count = getattr(gift_info, 'diamond_count', getattr(gift_info, 'price', 0))
                if not diamond_count:
                    diamond_count = getattr(gift_obj, 'diamond_count', getattr(gift_obj, 'price', getattr(gift_obj, 'diamondCount', 0)))
                
                total_coins = int(combo_count) * int(diamond_count)
                
                gift_icon = ""
                gift_image = getattr(gift_obj, 'image', getattr(gift_obj, 'icon', None))
                if gift_image:
                    urls = getattr(gift_image, 'url_list', []) or getattr(gift_image, 'urls', [])
                    if urls:
                        gift_icon = urls[0]

                message_text = f"Gönderdi: {gift_name}"
                
                gift_data = {
                    "gift_id": gift_id,
                    "gift_name": str(gift_name),
                    "gift_count": combo_count,
                    "gift_icon": str(gift_icon),
                    "total_coins": total_coins,
                    "unit_price": diamond_count
                }
                
                await parse_and_send(user_obj, message_text, msg_type="gift", gift_data=gift_data)

        try:
            print(f"[TikTok] {username} yayını kontrol ediliyor...")
            await client.start()
        except Exception as e:
            print(f"[TikTok] Yayın kapalı veya bağlantı koptu ({e}). 20 saniye sonra tekrar denenecek...")
        finally:
            # Önceki oturum arkada açık kalmasın
            try:
                await client.disconnect()
            except Exception:
                pass
        
        await asyncio.sleep(20)
