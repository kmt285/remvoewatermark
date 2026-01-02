import os
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# --- Render Health Check ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Watermark ဖျက်တဲ့ Logic အသစ် (Morphological Method) ---
async def remove_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    # ပုံရဲ့ Height, Width ကိုယူမယ်
    h, w, _ = img.shape

    # 1. Grayscale ပြောင်းမယ်
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Morphological Gradient ရှာမယ် (ဒါက စာသားတွေကို ပိုထင်ရှားစေတယ်)
    # Kernel Size (5,5) က စာလုံးအကြီးအသေးပေါ်မူတည်ပြီး ပြောင်းနိုင်တယ်
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    morph = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)

    # 3. Binarization (အဖြူ အမည်း သတ်မှတ်မယ်)
    # Otsu's thresholding က အလိုအလျောက် အကောင်းဆုံး threshold ကိုရှာပေးတယ်
    _, mask = cv2.threshold(morph, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # 4. Cleaning the Mask (အမည်းစက် သေးသေးမွှားမွှားတွေကို ဖယ်ထုတ်မယ်)
    # စာလုံးမဟုတ်တဲ့ အစက်အပျောက်တွေကို မဖျက်မိအောင်ပါ
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_clean)

    # 5. Expanding the Mask (စာလုံးရဲ့ အတွင်းသားတွေကိုပါ လွှမ်းခြုံအောင် Mask ကိုချဲ့မယ်)
    # Dilation လုပ်လိုက်ရင် စာလုံးအနားသတ်တင်မကဘဲ တစ်လုံးချင်းစီ ပြည့်သွားမယ်
    mask = cv2.dilate(mask, kernel, iterations=3)

    # 6. Region of Interest (ROI) - တစ်ပုံလုံးလျှောက်ဖျက်ရင် ရုပ်ပျက်တတ်လို့
    # အောက်ခြေနဲ့ အပေါ်ထိပ်နားက စာတွေကိုပဲ ဦးတည်ပြီးဖျက်မယ်
    # (Tiktok လို Watermark မျိုးအတွက် အဆင်ပြေအောင်)
    final_mask = np.zeros_like(mask)
    
    # ထိပ်ပိုင်း 20%
    final_mask[0:int(h*0.2), :] = mask[0:int(h*0.2), :]
    # အောက်ခြေ 30%
    final_mask[int(h*0.7):h, :] = mask[int(h*0.7):h, :]
    
    # ဘေးဘောင်တွေ (Optional) - လိုအပ်ရင် ဖွင့်သုံးနိုင်ပါတယ်
    # final_mask[:, 0:int(w*0.15)] = mask[:, 0:int(w*0.15)] # ဘယ်ဘက်ကပ်စာများ
    # final_mask[:, int(w*0.85):w] = mask[:, int(w*0.85):w] # ညာဘက်ကပ်စာများ

    # 7. Inpainting (ပုံဖျက်ပြီး အစားထိုးခြင်း)
    # Radius 5 ထားလိုက်တယ်၊ အရမ်းကြီးရင် ဝါးမယ်
    result = cv2.inpaint(img, final_mask, 5, cv2.INPAINT_TELEA)

    cv2.imwrite(output_path, result)
    return True

async def handle_photo(update: Update, context):
    if not update.message or not update.message.photo:
        return

    # User ကို စာပြန်မယ်
    msg = await update.message.reply_text("Watermark ဖျက်နေပါသည်... ⏳")

    try:
        file = await update.message.photo[-1].get_file()
        in_f = f"in_{update.message.message_id}.jpg"
        out_f = f"out_{update.message.message_id}.jpg"
        
        await file.download_to_drive(in_f)
        
        if await remove_watermark(in_f, out_f):
            await update.message.reply_photo(photo=open(out_f, 'rb'))
            await msg.delete()
        else:
            await msg.edit_text("ပုံကို ဖတ်မရပါ။")
            
        # Cleanup
        if os.path.exists(in_f): os.remove(in_f)
        if os.path.exists(out_f): os.remove(out_f)
            
    except Exception as e:
        print(f"Error: {e}")
        await msg.edit_text(f"Error ဖြစ်သွားပါတယ်: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_health_server, daemon=True).start()
    
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot Started...")
    app.run_polling()
