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
        # ✅ 1. Read the file bytes
        file_bytes = await file.read()
        
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded file payload is empty.")
        
        # ✅ 2. Try to validate it's an image (but don't convert)
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.load()
            detected_format = img.format
            print(f"✅ Valid image detected: {detected_format}")
        except Exception as e:
            # Don't fail - just accept the raw file
            detected_format = "unknown"
            print(f"⚠️ Could not validate image: {e}")
        
        # ✅ 3. Use the ORIGINAL file extension (don't convert!)
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_') or "image"
        timestamp = int(datetime.utcnow().timestamp())
        
        # ✅ 4. Keep the original file extension
        original_extension = os.path.splitext(file.filename)[1].lower() or ".jpg"
        filename = f"img_{timestamp}_{base_filename}{original_extension}"
        
        # ✅ 5. Upload the ORIGINAL bytes to GitHub (no conversion!)
        target_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"Upload image: {base_filename}",
            "content": base64.b64encode(file_bytes).decode("utf-8"),  # ✅ Uses ORIGINAL bytes
            "branch": BRANCH
        }
        
        response = requests.put(target_url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=500, 
                detail=f"GitHub upload failed: {response.text}"
            )
        
        # ✅ 6. Verify the file exists
        verify_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        verify_response = requests.get(verify_url, headers=headers)
        
        if verify_response.status_code != 200:
            raise HTTPException(
                status_code=500, 
                detail=f"File upload failed verification: {verify_response.text}"
            )
        
        # ✅ 7. Return URL with original extension
        raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True,
            "message": "File uploaded successfully!",
            "fileName": filename,
            "imageUrl": raw_url,
            "thumbnail_url": raw_url,
            "size": len(file_bytes),
            "format": detected_format,
            "verified": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")