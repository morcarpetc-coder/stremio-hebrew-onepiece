from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import requests
from deep_translator import GoogleTranslator
import urllib.parse
import time

app = FastAPI()

MANIFEST = {
    "id": "community.onepiece.hebrew.translator",
    "version": "1.0.5",
    "name": "וואן פיס - תרגום לעברית",
    "description": "גרסה יציבה: כולל תיקוני URL, מערכת Fallback למניעת קריסות 500, וייצוב תרגום מול גוגל.",
    "resources": ["subtitles"],
    "types": ["series", "movie", "anime", "other"]
}

@app.get("/manifest.json")
def get_manifest():
    return MANIFEST

@app.get("/subtitles/{path:path}")
def get_subtitles(request: Request):
    try:
        raw_path = request.scope.get("raw_path", b"").decode("utf-8")
        os_url = f"https://opensubtitles-v3.strem.io{raw_path}"
        
        headers = {"User-Agent": "Stremio/4.4"}
        response = requests.get(os_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {"subtitles": []}
            
        data = response.json()
        subtitles_list = data.get("subtitles", [])
        
        english_sub_url = None
        
        for sub in subtitles_list:
            if sub.get("lang") == "eng":
                english_sub_url = sub.get("url")
                break
        
        if not english_sub_url:
            return {"subtitles": []}
            
        encoded_url = requests.utils.quote(english_sub_url)
        base_url = str(request.base_url).rstrip('/')
        
        stream_id = "auto"
        if "tt" in raw_path:
            stream_id = "series"
        elif "kitsu" in raw_path:
            stream_id = "anime"
        
        return {
            "subtitles": [
                {
                    "id": f"heb_{stream_id}",
                    "url": f"{base_url}/translate-srt?url={encoded_url}",
                    "lang": "heb"
                }
            ]
        }
    except Exception:
        return {"subtitles": []}

@app.get("/translate-srt")
def translate_srt(url: str):
    original_srt_text = ""
    try:
        # התיקון הקריטי: שחזור הכתובת לפורמט תקין לפני ההורדה למניעת שגיאת 500
        clean_url = urllib.parse.unquote(url)
        
        srt_response = requests.get(clean_url, timeout=10)
        srt_response.encoding = 'utf-8' 
        original_srt_text = srt_response.text
        
        translated_text = translate_srt_content(original_srt_text)
        return Response(content=translated_text, media_type="text/srt; charset=utf-8")
    except Exception as e:
        print(f"Translation logic crashed: {e}")
        # רשת הביטחון: אם גוגל קרס, נחזיר את הכתובית באנגלית במקום שסטרימיו יקרוס
        if original_srt_text:
            return Response(content=original_srt_text, media_type="text/srt; charset=utf-8")
        return Response(content="1\n00:00:01,000 --> 00:00:05,000\n[System Error: Subtitles Unavailable]", media_type="text/srt; charset=utf-8")

def translate_srt_content(srt_text):
    translator = GoogleTranslator(source='en', target='he')
    lines = srt_text.splitlines()
    
    text_lines_indices = []
    text_to_translate = []
    
    for idx, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line or clean_line.isdigit() or "-->" in clean_line:
            continue
        text_lines_indices.append(idx)
        text_to_translate.append(line)
    
    batch_size = 40 
    for i in range(0, len(text_to_translate), batch_size):
        batch = text_to_translate[i:i+batch_size]
        try:
            translated_batch = translator.translate_batch(batch)
            for j, translated_text in enumerate(translated_batch):
                if translated_text:
                    actual_idx = text_lines_indices[i + j]
                    lines[actual_idx] = translated_text
        except Exception:
            # אם הייתה חסימה זמנית בתרגום קבוצה מסוימת, נדלג עליה (תישאר באנגלית) 
            pass
        # מרווח נשימה קטן כדי שגוגל לא יחסום את השרת על הצפות
        time.sleep(0.1) 
            
    return '\n'.join(lines)
