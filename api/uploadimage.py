import os
from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
from datetime import datetime

router = APIRouter(tags=["Upload Image"])

@router.post("/uploadimage")
async def upload_image(file: UploadFile = File(...)):
    try:
        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        file_path = f"uploads/{filename}"
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "success": True,
            "message": "File uploaded successfully",
            "url": f"/uploads/{filename}",
            "filename": filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")