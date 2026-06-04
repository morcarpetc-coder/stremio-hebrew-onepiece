from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import requests
from deep_translator import GoogleTranslator

app = FastAPI()

MANIFEST = {
    "id": "community.onepiece.hebrew.translator",
    "version": "1.0.1",
    "name": "וואן פיס - תרגום לעברית",
    "description": "מתרגם אוטומטית כתוביות מאנגלית לעברית עבור וואן פיס וסדרות אחרות",
    "resources": ["subtitles"],
    "types": ["series", "movie", "anime", "other"]
}

@app.get("/manifest.json")
def get_manifest():
    return MANIFEST

@app.get("/subtitles/{obj_type}/{stream_id}.json")
def get_subtitles(obj_type: str, stream_id: str, request: Request):
    try:
        os_url = f"https://opensubtitles-v3.strem.io/subtitles/{obj_type}/{stream_id}.json"
        response = requests.get(os_url, timeout=5)
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
        
        return {
            "subtitles": [
                {
                    "id": f"heb_auto_{stream_id}",
                    "url": f"{base_url}/translate-srt?url={encoded_url}",
                    "lang": "heb"
                }
            ]
        }
    except Exception:
        return {"subtitles": []}

@app.get("/translate-srt")
def translate_srt(url: str):
    try:
        srt_response = requests.get(url, timeout=10)
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
    
    batch_size = 50
    for i in range(0, len(text_to_translate), batch_size):
        batch = text_to_translate[i:i+batch_size]
        try:
            translated_batch = translator.translate_batch(batch)
            for j, translated_text in enumerate(translated_batch):
                actual_idx = text_lines_indices[i + j]
                lines[actual_idx] = translated_text
        except Exception:
            pass
            
    return '\n'.join(lines)
