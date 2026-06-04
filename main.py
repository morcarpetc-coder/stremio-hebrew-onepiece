from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import requests
from deep_translator import GoogleTranslator

app = FastAPI()

MANIFEST = {
    "id": "community.onepiece.hebrew.translator",
    "version": "1.0.4",
    "name": "וואן פיס - תרגום לעברית",
    "description": "מתרגם אוטומטית - גרסה מתקדמת הכוללת תיקון קידוד גולמי (Raw Path) לאנימה ולסדרות רגילות",
    "resources": ["subtitles"],
    "types": ["series", "movie", "anime", "other"]
}

@app.get("/manifest.json")
def get_manifest():
    return MANIFEST

# תופס כל בקשת כתוביות, לא משנה מה אורכה
@app.get("/subtitles/{path:path}")
def get_subtitles(request: Request):
    try:
        # פריצת הדרך: שאיבת הכתובת הגולמית בדיוק כפי שסטרימיו שלח, ללא פענוח אוטומטי של התווים
        raw_path = request.scope.get("raw_path", b"").decode("utf-8")
        
        # הרכבת הכתובת להעברה למאגר הרשמי של סטרימיו
        os_url = f"https://opensubtitles-v3.strem.io{raw_path}"
        
        # הוספת זהות של סטרימיו כדי למנוע חסימת בוטים
        headers = {"User-Agent": "Stremio/4.4"}
        response = requests.get(os_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {"subtitles": []}
            
        data = response.json()
        subtitles_list = data.get("subtitles", [])
        
        english_sub_url = None
        
        # חיפוש מקור אנגלי
        for sub in subtitles_list:
            if sub.get("lang") == "eng":
                english_sub_url = sub.get("url")
                break
        
        if not english_sub_url:
            return {"subtitles": []}
            
        encoded_url = requests.utils.quote(english_sub_url)
        base_url = str(request.base_url).rstrip('/')
        
        # חילוץ מזהה פשוט כדי שסטרימיו יציג את הלחצן
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
    except Exception as e:
        print(f"Server Error: {e}")
        return {"subtitles": []}

@app.get("/translate-srt")
def translate_srt(url: str):
    try:
        # שליפת קובץ ה-SRT וקידוד נכון למונע ג'יבריש
        srt_response = requests.get(url, timeout=10)
        srt_response.encoding = 'utf-8' 
        srt_text = srt_response.text
        
        translated_text = translate_srt_content(srt_text)
        
        return Response(content=translated_text, media_type="text/srt; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    
    # הקטנת קבוצות התרגום ל-40 כדי להבטיח יציבות ולא לקרוס מול גוגל
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
            pass
            
    return '\n'.join(lines)
