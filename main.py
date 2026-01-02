import os
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# --- Health Check ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Blur & Add Text Logic ---
async def process_image(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    
    # ==========================================
    # ချိန်ညှိရန် နေရာ (Settings)
    # ==========================================
    BOX_WIDTH_PCT = 0.35   # Box အကျယ် (35%)
    BOX_HEIGHT_PCT = 0.08  # Box အမြင့် (8%)
    NEW_TEXT = "@moviesbydatahouse" # အသစ်ထည့်မည့် စာသား
    # ==========================================

    # ၁။ Box နေရာ တွက်ချက်ခြင်း
    center_x, center_y = w // 2, h // 2
    box_w = int(w * BOX_WIDTH_PCT)
    box_h = int(h * BOX_HEIGHT_PCT)
    
    x1 = center_x - (box_w // 2)
    x2 = center_x + (box_w // 2)
    y1 = center_y - (box_h // 2)
    y2 = center_y + (box_h // 2)

    # Boundary Checks
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)

    # ၂။ Gaussian Blur လုပ်ခြင်း
    roi = img[y1:y2, x1:x2]
    # ဝါးအားကို (99, 99), 30 ထားထားပါတယ်
    blurred_roi = cv2.GaussianBlur(roi, (99, 99), 30)
    img[y1:y2, x1:x2] = blurred_roi

    # ၃။ စာသား အသစ်ထည့်ခြင်း (အံဝင်ခွင်ကျဖြစ်အောင် တွက်ချက်ခြင်း)
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 2
    
    # (က) Font Scale တွက်မယ် (Box အကျယ်ရဲ့ ၉၀% လောက်ပြည့်အောင်)
    target_text_width = box_w * 0.9
    # အရင်ဆုံး scale 1.0 မှာ ဘယ်လောက်ကျယ်လဲ စမ်းတိုင်းကြည့်မယ်
    (base_w, base_h), baseline = cv2.getTextSize(NEW_TEXT, font, 1.0, thickness)
    # လိုချင်တဲ့ အကျယ်ရဖို့ ဘယ်လောက် scale လုပ်ရမလဲ တွက်မယ်
    font_scale = target_text_width / base_w
    
    # (ခ) အမှန်တကယ်ရလာမယ့် စာလုံးဆိုဒ်ကို ပြန်တွက်မယ်
    (text_w, text_h), baseline = cv2.getTextSize(NEW_TEXT, font, font_scale, thickness)
    
    # (ဂ) စာလုံးကို Box အလယ်တည့်တည့်ထားဖို့ နေရာတွက်မယ်
    text_x = int(x1 + (box_w - text_w) / 2)
    # Y နေရာတွက်တာ နည်းနည်းရှုပ်တယ် (baseline ကြောင့်)
    text_y = int(y1 + (box_h + text_h) / 2)

    # (ဃ) စာရေးမယ် (ထင်းအောင် ၂ ထပ်ရေးမယ်)
    # အလွှာ ၁ - အနားသတ် အမည်းရောင် (Outline)
    cv2.putText(img, NEW_TEXT, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
    # အလွှာ ၂ - စာလုံး အဖြူရောင် (Main Text)
    cv2.putText(img, NEW_TEXT, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    cv2.imwrite(output_path, img)
    return True

async def handle_photo(update: Update, context):
    if not update.message or not update.message.photo:
        return

    msg = await update.message.reply_text("ဝါးပြီး စာထည့်နေပါသည်... ⏳")

    try:
        file = await update.message.photo[-1].get_file()
        in_f = f"in_{update.message.message_id}.jpg"
        out_f = f"out_{update.message.message_id}.jpg"
        
        await file.download_to_drive(in_f)
        
        if await process_image(in_f, out_f):
            await update.message.reply_photo(photo=open(out_f, 'rb'))
            await msg.delete()
        else:
            await msg.edit_text("Error processing image.")
            
        if os.path.exists(in_f): os.remove(in_f)
        if os.path.exists(out_f): os.remove(out_f)
            
    except Exception as e:
        print(f"Error: {e}")
        await msg.edit_text(f"Error: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_health_server, daemon=True).start()
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot Started (Blur + Text Mode)...")
    app.run_polling()
