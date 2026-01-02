import os
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# --- Render အတွက် Dummy Web Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Watermark ဖျက်တဲ့ Logic ---
async def remove_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    
    # ၁။ စာသားဧရိယာကို အစပိုင်းကထက် နည်းနည်းပဲ ပိုချဲ့မယ် (Subtle expansion)
    cy1, cy2 = int(h * 0.35), int(h * 0.65) 
    cx1, cx2 = int(w * 0.25), int(w * 0.75)
    
    # ၂။ စာသားကို ရှာတဲ့နေရာမှာ ပိုတိကျအောင် Threshold ကို တိုးလိုက်ပါမယ်
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # ၂၀၀ အစား ၂၂၀ သုံးခြင်းဖြင့် စာသားအစစ်ကိုပဲ ပိုဖမ်းမိစေပါတယ်
    _, mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY) 
    
    final_mask = np.zeros_like(mask)
    final_mask[cy1:cy2, cx1:cx2] = mask[cy1:cy2, cx1:cx2]
    
    # ၃။ ဧရိယာချဲ့တာကို အနည်းဆုံး (၁ pixel) ပဲ ထားပါမယ်
    kernel = np.ones((2,2), np.uint8)
    final_mask = cv2.dilate(final_mask, kernel, iterations=1)
    
    # ၄။ Inpaint Radius ကို လျှော့ချခြင်း (ပုံမဝါးအောင်)
    # ၇ အစား ၃ ကို ပြန်သုံးပါမယ်။ ဒါမှ ပုံရိပ်တွေ မကွဲမှာပါ
    result = cv2.inpaint(img, final_mask, 3, cv2.INPAINT_TELEA)
    
    cv2.imwrite(output_path, result)
    return True

async def handle_photo(update: Update, context):
    file = await update.message.photo[-1].get_file()
    in_f, out_f = f"in_{update.message.message_id}.jpg", f"out_{update.message.message_id}.jpg"
    await file.download_to_drive(in_f)
    if await remove_watermark(in_f, out_f):
        await update.message.reply_photo(photo=open(out_f, 'rb'))
    os.remove(in_f); os.remove(out_f)

if __name__ == '__main__':
    # Web Server ကို Thread တစ်ခုနဲ့ သီးသန့် run ထားမယ်
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # Telegram Bot ကို Run မယ်
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()



