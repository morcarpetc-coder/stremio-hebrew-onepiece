from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import requests
from deep_translator import GoogleTranslator
import urllib.parse

app = FastAPI()

MANIFEST = {
    "id": "community.onepiece.hebrew.translator",
    "version": "1.1.1",
    "name": "וואן פיס - תרגום לעברית (אולטימטיבי)",
    "description": "גרסה 1.1.1: מעבר לשרתי ElfHosted הפעילים עבור חילוץ כתוביות MKV של אנימה",
    "resources": ["subtitles"],
    "types": ["series", "movie", "anime", "other"]
}

# רשימת ספקי הכתוביות המעודכנת
PROVIDERS = [
    "https://opensubtitles-v3.strem.io",      # ספק 1: סדרות וסרטים רגילים 
    "https://animetosho.elfhosted.com"        # ספק 2: הכתובת החדשה והפעילה לחילוץ MKV!
]

@app.get("/manifest.json")
def get_manifest():
    return MANIFEST

@app.get("/subtitles/{path:path}")
def get_subtitles(request: Request):
    try:
        raw_path = request.scope.get("raw_path", b"").decode("utf-8")
        english_sub_url = None
        
        # לולאה שרצה על ספקי הכתוביות
        for provider in PROVIDERS:
            os_url = f"{provider}{raw_path}"
            print(f"DEBUG: Trying provider -> {os_url}")
            
            try:
                headers = {"User-Agent": "Stremio/4.4"}
                # Timeout של 8 שניות כדי לא להיתקע יותר מדי על ספק שלא מגיב
                response = requests.get(os_url, headers=headers, timeout=8)
                
                if response.status_code == 200:
                    data = response.json()
                    subtitles_list = data.get("subtitles", [])
                    
                    for sub in subtitles_list:
                        lang = sub.get("lang", "").lower()
                        if lang == "eng" or lang == "en":
                            english_sub_url = sub.get("url")
                            print(f"DEBUG: Success! Found English subtitle at {provider}")
                            break
            except Exception as e:
                print(f"DEBUG: Provider {provider} failed: {e}")
            
            if english_sub_url:
                break
        
        if not english_sub_url:
            print("DEBUG: No English subtitle found in any provider.")
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
        print(f"DEBUG: Server crashed in get_subtitles: {e}")
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
    
    for idx, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line or clean_line.isdigit() or "-->" in clean_line:
            continue
        text_lines_indices.append(idx)
        text_to_translate.append(line)
    
    chunk_size = 100 
    for i in range(0, len(text_to_translate), chunk_size):
        batch = text_to_translate[i:i+chunk_size]
        combined_text = '\n'.join(batch)
        
        try:
            translated_combined = translator.translate(combined_text)
            translated_batch = translated_combined.split('\n')
            
            for j in range(min(len(batch), len(translated_batch))):
                actual_idx = text_lines_indices[i + j]
                lines[actual_idx] = translated_batch[j].strip()
        except Exception as e:
            print(f"DEBUG: Chunk {i} failed: {e}")
            pass
            
    return '\n'.join(lines)
