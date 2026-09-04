import os
import io
import base64
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, status
import requests
import pymysql
from PIL import Image

router = APIRouter(tags=["Global Image Optimization"])

# Get environment variables with defaults
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "ogdoraaranyas-source")         
REPO_NAME = os.getenv("GITHUB_REPO_NAME", "restfullapis")               
BRANCH = os.getenv("GITHUB_BRANCH", "main")

# Allowed image types
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Database link failed: {str(e)}"
        )

@router.post("/uploadimage")
async def upload_general_image(file: UploadFile = File(...)):
    """
    Upload and optimize an image to GitHub repository
    """
    # Validate GitHub token exists
    if not GITHUB_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="GITHUB_TOKEN environment variable is not set. Please add it to Vercel environment variables."
        )

    # Validate file type
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validate file size (max 5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Seek back to start
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: 5MB"
        )

    try:
        # 1. Read and optimize the image
        file_bytes = await file.read()
        img = Image.open(io.BytesIO(file_bytes))
        
        # Check if image is valid
        if img.width == 0 or img.height == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image dimensions"
            )
        
        # Optimize image to WebP
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="WEBP", quality=75, optimize=True)
        optimized_bytes = output_buffer.getvalue()
        
        # 2. Encode to base64
        encoded_content = base64.b64encode(optimized_bytes).decode("utf-8")
        
        # 3. Generate filename with sanitization
        base_filename = "".join(c for c in os.path.splitext(file.filename)[0] if c.isalnum() or c in " _-")
        base_filename = base_filename.replace(' ', '_')
        timestamp = int(datetime.utcnow().timestamp())
        filename = f"img_{timestamp}_{base_filename}.webp"
        
        # 4. GitHub API URL
        github_api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/categoryimages/{filename}"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 5. Check if file already exists
        existing_file_response = requests.get(github_api_url, headers=headers)
        
        # 6. Prepare payload
        payload = {
            "message": f"Upload: {filename}",
            "content": encoded_content,
            "branch": BRANCH
        }
        
        # If file exists, include sha to update it
        if existing_file_response.status_code == 200:
            existing_data = existing_file_response.json()
            payload["sha"] = existing_data.get("sha")
        elif existing_file_response.status_code not in [200, 404]:
            # If we get any other error, log it but continue
            print(f"GitHub check response: {existing_file_response.status_code} - {existing_file_response.text}")
        
        # 7. Upload to GitHub
        response = requests.put(github_api_url, json=payload, headers=headers)
        
        # 8. Check response
        if response.status_code not in [200, 201]:
            error_detail = f"GitHub upload failed: {response.text}"
            if response.status_code == 401:
                error_detail = "GitHub authentication failed. Please check your GITHUB_TOKEN has 'repo' scope."
            elif response.status_code == 403:
                error_detail = "GitHub access forbidden. Token may not have write permissions or repository is private."
            elif response.status_code == 404:
                error_detail = f"Repository '{REPO_OWNER}/{REPO_NAME}' or path 'categoryimages/' not found. Please create the folder first."
            elif response.status_code == 422:
                error_detail = f"Invalid request. Make sure the file path is valid. Error: {response.text}"
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=error_detail
            )
        
        # 9. Generate CDN URL
        production_cdn_url = f"https://statically.io/gh/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/categoryimages/{filename}"
        
        # 10. Return success response
        return {
            "success": True, 
            "message": "Image compressed to WebP and live on CDN!",
            "filename": filename,
            "thumbnail_url": production_cdn_url,
            "size": len(optimized_bytes),
            "original_size": file_size
        }
        
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        print(f"Network error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Network error while uploading to GitHub: {str(e)}"
        )
    except Exception as e:
        print(f"Error in upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Image processing failed: {str(e)}"
        )