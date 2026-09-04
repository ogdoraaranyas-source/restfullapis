import os
import io
import base64
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
import requests
import pymysql
from PIL import Image  # Added compression library utility hooks

router = APIRouter(tags=["Categories Management"])

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

@router.post("/upload-image")
async def upload_category_image(file: UploadFile = File(...)):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=500, detail="Vercel Environment Variable 'GITHUB_TOKEN' is missing.")

    try:
        # 1. Read the raw 5MB file byte stream into memory safely
        file_bytes = await file.read()
        
        # 2. Open the image with Pillow to execute optimization processes
        img = Image.open(io.BytesIO(file_bytes))
        
        # 3. Dynamic Resize Matrix: Downsize if image bounds exceed modern standards
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        # 4. Convert the image context into the highly compressed web-native .webp profile
        output_buffer = io.BytesIO()
        # Save as WebP with 75% quality optimization ratio (Shrinks 5MB down to ~150KB!)
        img.save(output_buffer, format="WEBP", quality=75)
        optimized_bytes = output_buffer.getvalue()
        
        # 5. Base64 Encode the newly optimized tiny asset bytes for GitHub API
        encoded_content = base64.b64encode(optimized_bytes).decode("utf-8")
        
        # Extract name without extension and force append the new .webp string extension path
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_')
        filename = f"cat_{int(datetime.utcnow().timestamp())}_{base_filename}.webp"
        
        target_url = f"https://github.com{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"Optimized Admin Upload: {filename}",
            "content": encoded_content,
            "branch": BRANCH
        }
        
        # 6. Stream upload the optimized lightweight file directly to GitHub
        response = requests.put(target_url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            raise HTTPException(status_code=500, detail=f"GitHub repository upload failed: {response.text}")
            
        # 7. Generate your final high-speed Statically CDN production URL link target path
        production_cdn_url = f"https://statically.io{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True, 
            "message": "Image compressed, converted to WebP, and saved successfully!",
            "thumbnail_url": production_cdn_url
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing compression pipeline failed: {str(e)}")
