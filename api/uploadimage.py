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
        
        # ✅ 3. Debug - print file info
        print(f"Received file: {file.filename}")
        print(f"Content type: {file.content_type}")
        print(f"File size: {len(file_bytes)} bytes")
        print(f"First 10 bytes: {file_bytes[:10]}")
        
        # ✅ 4. Try to detect image format from bytes (more flexible like Node.js sharp)
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.load()  # Force loading to validate
        except UnidentifiedImageError:
            # Try to detect if it's actually a different format
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid image file. File starts with: {file_bytes[:10].hex()}. Please upload a valid JPG, PNG, GIF, etc."
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Unable to process the image: {str(e)}"
            )
        
        print(f"✅ Image detected as: {img.format}")
        
        # 5. Downsize bounds in memory cleanly (like sharp.rotate().webp().toBuffer())
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        # 6. Compress directly into a raw bytes memory buffer stream
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="WEBP", quality=85)  # Same quality as Node.js
        optimized_bytes = output_buffer.getvalue()
        
        # 7. Convert memory stream to base64 string
        encoded_content = base64.b64encode(optimized_bytes).decode("utf-8")
        
        base_filename = os.path.splitext(file.filename)[0].replace(' ', '_') or "image"
        filename = f"img_{int(datetime.utcnow().timestamp())}_{base_filename}.webp"
        
        # ✅ Correct GitHub API Endpoint (same as Octokit in Node.js)
        target_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"Upload venue image: {base_filename}",
            "content": encoded_content,
            "branch": BRANCH
        }
        
        # 8. Push to GitHub (same as octokit.repos.createOrUpdateFileContents)
        response = requests.put(target_url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            raise HTTPException(status_code=500, detail=f"GitHub repository upload failed: {response.text}")
            
        # ✅ Correct CDN URL format (same as raw.githubusercontent.com in Node.js)
        raw_image_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        # Also provide Statically CDN URL for better performance
        production_cdn_url = f"https://statically.io/gh/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        return {
            "success": True, 
            "message": "Image uploaded successfully!",
            "fileName": filename,
            "path": f"categoryimages/{filename}",
            "imageUrl": raw_image_url,
            "thumbnail_url": production_cdn_url,
            "content_type": file.content_type,
            "detected_format": img.format,
            "size_original": len(file_bytes),
            "size_optimized": len(optimized_bytes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing compression pipeline failed: {str(e)}")