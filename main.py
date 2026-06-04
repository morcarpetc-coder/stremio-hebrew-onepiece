from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import requests
from deep_translator import GoogleTranslator
import urllib.parse

app = FastAPI()

MANIFEST = {
    "id": "community.onepiece.hebrew.translator",
    "version": "1.0.8",
    "name": "וואן פיס - תרגום לעברית",
    "description": "גרסה 1.0.8: מצב טורבו - תרגום מהיר בבלוקים למניעת ניתוקי Timeout מול סטרימיו",
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
        
        print(f"DEBUG: Requesting -> {os_url}")
        
        headers = {"User-Agent": "Stremio/4.4"}
        response = requests.get(os_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {"subtitles": []}
            
        data = response.json()
        subtitles_list = data.get("subtitles", [])
        
        english_sub_url = None
        for sub in subtitles_list:
            lang = sub.get("lang", "").lower()
            if lang == "eng" or lang == "en":
                english_sub_url = sub.get("url")
                break
        
        if not english_sub_url:
            print("DEBUG: No English subtitle found.")
            return {"subtitles": []}
            
        encoded_url = requests.utils.quote(english_sub_url)
        base_url = str(request.base_url).rstrip('/')
        if base_url.startswith("http://") and "onrender.com" in base_url:
            base_url = base_url.replace("http://", "https://")
            
        stream_id = "auto"
        if "tt" in raw_path:
            stream_id = "series"
        elif "kitsu" in raw_path:
            stream_id = "anime"
        
        final_url = f"{base_url}/translate-srt?url={encoded_url}"
        
        return {
            "subtitles": [
                {
                    "id": f"heb_{stream_id}",
                    "url": final_url,
                    "lang": "heb"
                }
            ]
        }
    except Exception as e:
        print(f"DEBUG: Server crashed: {e}")
        return {"subtitles": []}

@app.get("/translate-srt")
def translate_srt(url: str):
    print("DEBUG: Stremio requested translation. Starting Turbo Mode...")
    original_srt_text = ""
    try:
        clean_url = urllib.parse.unquote(url)
        
        srt_response = requests.get(clean_url, timeout=10)
        srt_response.encoding = 'utf-8' 
        original_srt_text = srt_response.text
        
        translated_text = translate_srt_content(original_srt_text)
        print("DEBUG: Translation finished successfully!")
        
        return Response(content=translated_text, media_type="text/srt; charset=utf-8")
    except Exception as e:
        print(f"DEBUG: Translation logic crashed: {e}")
        if original_srt_text:
            return Response(content=original_srt_text, media_type="text/srt; charset=utf-8")
        return Response(content="1\n00:00:01,000 --> 00:00:05,000\n[System Error]", media_type="text/srt; charset=utf-8")

def translate_srt_content(srt_text):
    translator = GoogleTranslator(source='en', target='iw')
    lines = srt_text.splitlines()
    
    text_lines_indices = []
    text_to_translate = []
    
    # חילוץ הטקסט בלבד
    for idx, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line or clean_line.isdigit() or "-->" in clean_line:
            continue
        text_lines_indices.append(idx)
        text_to_translate.append(line)
    
    # שיטת הטורבו: שליחת גושים גדולים שלמים במכה אחת במקום שורות בודדות
    chunk_size = 100 
    for i in range(0, len(text_to_translate), chunk_size):
        batch = text_to_translate[i:i+chunk_size]
        # איחוד השורות לטקסט אחד ארוך מופרד בירידת שורה
        combined_text = '\n'.join(batch)
        
        try:
            # בקשה אחת בודדת לגוגל עבור 100 שורות!
            translated_combined = translator.translate(combined_text)
            translated_batch = translated_combined.split('\n')
            
            # החזרת הטקסט למקום המדויק
            for j in range(min(len(batch), len(translated_batch))):
                actual_idx = text_lines_indices[i + j]
                lines[actual_idx] = translated_batch[j].strip()
        except Exception as e:
            print(f"DEBUG: Chunk {i} failed: {e}")
            pass
            
    return '\n'.join(lines)
