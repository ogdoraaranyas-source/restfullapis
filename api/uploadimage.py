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
        
        # ✅ 1. Open the image
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.load()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")
        
        # ✅ 2. Resize if needed
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        # ✅ 3. Save as PNG (NOT WebP - this fixes the display issue)
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="PNG", quality=95)  # PNG is universal
        optimized_bytes = output_buffer.getvalue()
        
        # ✅ 4. Verify the file is valid BEFORE uploading
        try:
            test_img = Image.open(io.BytesIO(optimized_bytes))
            test_img.load()
            print(f"✅ Valid image detected: {test_img.format}, size: {len(optimized_bytes)} bytes")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image conversion failed: {str(e)}")
        
        # ✅ 5. Create filename with correct extension
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_') or "image"
        timestamp = int(datetime.utcnow().timestamp())
        filename = f"img_{timestamp}_{base_filename}.png"  # Changed to .png
        
        # ✅ 6. Upload to GitHub
        target_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
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
        
        try:
            github_file_url = response.json().get("content", {}).get("html_url", "")
        except:
            github_file_url = ""

        # ✅ 7. Use Raw URL for display (works perfectly with PNG)
        raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True,
            "message": "File uploaded successfully!",
            "fileName": filename,
            "imageUrl": raw_url,
            "thumbnail_url": raw_url,  # ✅ Use raw_url for guaranteed display
            "size": len(optimized_bytes),
            "githubUrl": github_file_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")