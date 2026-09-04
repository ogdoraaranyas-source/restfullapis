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
        # ✅ 1. Reset file pointer
        await file.seek(0)
        
        # 2. Read bytes
        file_bytes = await file.read()
        
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded file payload is empty.")
        
        # ✅ 3. Let Pillow validate the image (removed strict content-type check)
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # Verify it's a valid image
            img = Image.open(io.BytesIO(file_bytes))  # Reopen after verification
        except UnidentifiedImageError:
            raise HTTPException(
                status_code=400, 
                detail="The uploaded file is not a valid image. Please upload a proper image file."
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Unable to process the image: {str(e)}"
            )
        
        # 4. Downsize bounds in memory cleanly
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        # 5. Compress directly into a raw bytes memory buffer stream
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="WEBP", quality=75)
        optimized_bytes = output_buffer.getvalue()
        
        # 6. Convert memory stream to base64 string
        encoded_content = base64.b64encode(optimized_bytes).decode("utf-8")
        
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_') or "image"
        filename = f"img_{int(datetime.utcnow().timestamp())}_{base_filename}.webp"
        
        # ✅ Correct GitHub API Endpoint
        target_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"Admin Panel Media Asset Pushed: {filename}",
            "content": encoded_content,
            "branch": BRANCH
        }
        
        # 7. Push to GitHub
        response = requests.put(target_url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            raise HTTPException(status_code=500, detail=f"GitHub repository upload failed: {response.text}")
            
        # Correct CDN URL format
        production_cdn_url = f"https://statically.io/gh/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True, 
            "message": "Image compressed to WebP and live on CDN!",
            "thumbnail_url": production_cdn_url,
            "filename": filename,
            "content_type": file.content_type,
            "size_original": len(file_bytes),
            "size_optimized": len(optimized_bytes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing compression pipeline failed: {str(e)}")