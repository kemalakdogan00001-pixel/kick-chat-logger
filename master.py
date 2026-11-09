import os
import json
import asyncio
from aiohttp import web

# Botları modüllerden içeri aktarıyoruz
from tiktok_bot import start_tiktok_bot
from kick_bot import start_kick_bot

KICK_USERNAME = os.environ.get("KICK_USERNAME", "buluayz")
TIKTOK_USERNAME = os.environ.get("TIKTOK_USERNAME", "@mbulucii2hg")

# Botların sunucu üzerinde çalışıp çalışmayacağını belirler (Varsayılan: true)
RUN_BOTS_ON_SERVER = os.environ.get("RUN_BOTS", "true").lower() == "true"

# Bellekte hem TikTok hem Kick mesajlarını tutacak ortak liste (Maksimum 250 mesaj)
chat_history = []
connected_clients = set()

async def add_to_history(data):
    chat_history.append(data)
    if len(chat_history) > 250:
        chat_history.pop(0)

async def broadcast_message(data):
    if connected_clients:
        message_json = json.dumps(data)
        dead_clients = set()
        for ws in list(connected_clients):
            try:
                await ws.send_str(message_json)
            except Exception:
                dead_clients.add(ws)
        connected_clients.difference_update(dead_clients)

# ---------------------------------------------------------
# ORTAK CALLBACK (Veri İşleyici)
# ---------------------------------------------------------
async def on_new_message(data):
    await add_to_history(data)
    await broadcast_message(data)

# ---------------------------------------------------------
# TEK PORT HEM HTML HEM WEBSOCKET YÖNETİMİ
# ---------------------------------------------------------
async def handle_root(request):
    # Gelen istek bir WebSocket bağlantısıysa
    if request.headers.get("Upgrade", "").lower() == "websocket":
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        connected_clients.add(ws)

        # Yeni biri bağlandığında (veya F5 atıldığında) geçmiş mesajları gönder
        try:
            history_payload = json.dumps({"type": "history", "messages": chat_history})
            await ws.send_str(history_payload)
        except Exception as e:
            print(f"Geçmiş gönderim hatası: {e}")

        try:
            # Dışarıdan (Relay/Köprü modunda) mesaj gönderilirse alıp tüm istemcilere dağıtır
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        incoming_data = json.loads(msg.data)
                        if incoming_data.get("type") in ("chat", "gift"):
                            await on_new_message(incoming_data)
                    except Exception:
                        pass
        finally:
            connected_clients.discard(ws)
        return ws

    # Normal tarayıcı isteğiyse doğrudan index.html dosyasını sun
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return web.FileResponse(os.path.join(base_dir, "index.html"))

async def start_background_bots(app):
    if RUN_BOTS_ON_SERVER:
        print(f"Dinlenen Kanallar | Kick: {KICK_USERNAME} | TikTok: {TIKTOK_USERNAME}")
        app["tiktok_task"] = asyncio.create_task(start_tiktok_bot(TIKTOK_USERNAME, on_new_message))
        app["kick_task"] = asyncio.create_task(start_kick_bot(KICK_USERNAME, on_new_message))
    else:
        print("Sunucu Köprü (Relay) Modunda Başlatıldı. Dışarıdan veri bekleniyor...")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.on_startup.append(start_background_bots)

    port = int(os.environ.get("PORT", 8765))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"Master Sunucu Hazır (http://localhost:{port} ve ws://localhost:{port})")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())