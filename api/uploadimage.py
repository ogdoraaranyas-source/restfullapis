import os
import io
import base64
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
import requests
import pymysql
from PIL import Image

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
        file_bytes = await file.read()
        
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded file payload is empty.")
        
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.load()
            
            max_size = 1024
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="WEBP", quality=85)
            optimized_bytes = output_buffer.getvalue()
            
        except Exception as e:
            optimized_bytes = file_bytes
        
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_') or "image"
        timestamp = int(datetime.utcnow().timestamp())
        filename = f"img_{timestamp}_{base_filename}.webp"
        
        # ✅ CORRECT: Use "token" for Classic tokens (NOT "Bearer")
        target_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",  # ✅ For Classic Token
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"Upload image: {base_filename}",
            "content": base64.b64encode(optimized_bytes).decode("utf-8"),
            "branch": BRANCH
        }
        
        response = requests.put(target_url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            print(f"GitHub response: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=500, 
                detail=f"GitHub upload failed: {response.text}"
            )
        
        # ✅ FIX: Safely get the GitHub URL - don't crash if 'content' is missing
        try:
            github_file_url = response.json().get("content", {}).get("html_url", "")
        except:
            github_file_url = ""

        raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        cdn_url = f"https://statically.io/gh/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True,
            "message": "File uploaded successfully!",
            "fileName": filename,
            "imageUrl": raw_url,
            "thumbnail_url": cdn_url,
            "size": len(optimized_bytes),
            "githubUrl": github_file_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")