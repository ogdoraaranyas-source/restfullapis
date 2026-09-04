import os
import io
import base64
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
import requests
import pymysql
from PIL import Image, UnidentifiedImageError

router = APIRouter(tags=["Global Image Optimization"])

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "ogdoraaranyas-source"         
REPO_NAME = "restfullapis"               
BRANCH = "main"

def get_db_connection():
    try:
        return pymysql.connect(
            host=os.getenv("TIDB_HOST"),
            user=os.getenv("TIDB_USER"),
            password=os.getenv("TIDB_PASSWORD"),
            database=os.getenv("TIDB_DB"),
            port=4000,
            ssl={"ssl_disabled": False}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database link failed: {str(e)}")

@router.post("/uploadimage")
async def upload_general_image(file: UploadFile = File(...)):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=500, detail="Vercel Environment Variable 'GITHUB_TOKEN' is missing.")

    try:
        # ✅ 1. Read the file with async - this is critical for Vercel
        file_bytes = await file.read()
        
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded file payload is empty.")
        
        # ✅ 2. Debug logging
        print(f"File: {file.filename}")
        print(f"Size: {len(file_bytes)} bytes")
        print(f"Bytes start: {file_bytes[:20].hex()}")
        
        # ✅ 3. Try to process as image with fallback
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.load()
            print(f"✅ Detected format: {img.format}")
            
            # Process image
            max_size = 1024
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="WEBP", quality=85)
            optimized_bytes = output_buffer.getvalue()
            
        except Exception as e:
            print(f"⚠️ Image processing failed: {e}")
            # Fallback: upload original bytes as-is
            optimized_bytes = file_bytes
            print("Uploading original file as-is")
        
        # ✅ 4. Create filename
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_') or "image"
        timestamp = int(datetime.utcnow().timestamp())
        filename = f"img_{timestamp}_{base_filename}.webp"
        
        # ✅ 5. Upload to GitHub
        encoded_content = base64.b64encode(optimized_bytes).decode("utf-8")
        
        target_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"Upload image: {base_filename}",
            "content": encoded_content,
            "branch": BRANCH
        }
        
        response = requests.put(target_url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            raise HTTPException(status_code=500, detail=f"GitHub upload failed: {response.text}")
        
        # ✅ 6. Return response
        raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        cdn_url = f"https://statically.io/gh/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True,
            "message": "File uploaded successfully!",
            "fileName": filename,
            "imageUrl": raw_url,
            "thumbnail_url": cdn_url,
            "size": len(optimized_bytes),
            "detected_format": img.format if 'img' in locals() else "unknown"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")