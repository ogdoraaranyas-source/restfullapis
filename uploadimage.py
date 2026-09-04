import os
import io
import base64
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
import requests
import pymysql
from PIL import Image

# Tags group these nicely inside your FastAPI documentation UI
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

@router.post("/upload-image")
async def upload_general_image(file: UploadFile = File(...)):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=500, detail="Vercel Environment Variable 'GITHUB_TOKEN' is missing.")

    try:
        file_bytes = await file.read()
        img = Image.open(io.BytesIO(file_bytes))
        
        # Max resolution limits for high performance fluid layout views
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="WEBP", quality=75)
        optimized_bytes = output_buffer.getvalue()
        
        encoded_content = base64.b64encode(optimized_bytes).decode("utf-8")
        
        # Pull base string cleanly to force web-optimized conversion extension paths
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_')
        filename = f"img_{int(datetime.utcnow().timestamp())}_{base_filename}.webp"
        
        # FIXED: Corrected endpoints to avoid route parsing abort loops on Linux servers
        target_url = f"https://github.com{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"Admin Panel Media Asset Pushed: {filename}",
            "content": encoded_content,
            "branch": BRANCH
        }
        
        response = requests.put(target_url, json=payload, headers=headers)
        
        if response.status_code not in:
            raise HTTPException(status_code=500, detail=f"GitHub repository upload failed: {response.text}")
            
        # FIXED: Formatted exactly to match official Statically subdomains for open-source Git CDNs
        production_cdn_url = f"https://statically.io{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True, 
            "message": "Image compressed to WebP and live on CDN!",
            "thumbnail_url": production_cdn_url
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing compression pipeline failed: {str(e)}")
