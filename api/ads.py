import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import pymysql

router = APIRouter(tags=["Ads Management"])

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

class AdCreate(BaseModel):
    thumburl: Optional[str] = None
    categoryid: int
    categoryname: str

class AdUpdate(BaseModel):
    thumburl: Optional[str] = None
    categoryid: Optional[int] = None
    categoryname: Optional[str] = None

# 📥 1. Create Ad
@router.post("/ads")
def create_ad(ad_data: AdCreate):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO ads (thumburl, categoryid, categoryname, created_at) 
                VALUES (%s, %s, %s, NOW())
            """
            cursor.execute(sql, (
                ad_data.thumburl, ad_data.categoryid, ad_data.categoryname
            ))
            connection.commit()
            ad_id = cursor.lastrowid
            
            return {"success": True, "message": "Ad created successfully!", "ad_id": ad_id}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# 📋 2. Get All Ads
@router.get("/ads")
def get_all_ads():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SELECT id, thumburl, categoryid, categoryname, created_at FROM ads ORDER BY id ASC"
            cursor.execute(sql)
            ads = cursor.fetchall()
            
            for ad in ads:
                if ad.get('created_at') and isinstance(ad['created_at'], datetime):
                    ad['created_at'] = ad['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    
        return {"success": True, "ads": ads}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# 🔍 3. Get Single Ad
@router.get("/ads/{ad_id}")
def get_ad(ad_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SELECT id, thumburl, categoryid, categoryname, created_at FROM ads WHERE id = %s"
            cursor.execute(sql, (ad_id,))
            ad = cursor.fetchone()
            
            if not ad:
                raise HTTPException(status_code=404, detail="Ad not found")
            
            if ad.get('created_at') and isinstance(ad['created_at'], datetime):
                ad['created_at'] = ad['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    
        return {"success": True, "ad": ad}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# 📝 4. Update Ad
@router.put("/ads/{ad_id}")
def update_ad(ad_id: int, ad_data: AdUpdate):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM ads WHERE id = %s", (ad_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Ad not found")

            update_fields = []
            params = []
            
            if ad_data.thumburl is not None:
                update_fields.append("thumburl = %s")
                params.append(ad_data.thumburl)
            if ad_data.categoryid is not None:
                update_fields.append("categoryid = %s")
                params.append(ad_data.categoryid)
            if ad_data.categoryname is not None:
                update_fields.append("categoryname = %s")
                params.append(ad_data.categoryname)

            if not update_fields:
                return {"success": True, "message": "No modification parameters specified."}

            params.append(ad_id)
            sql = f"UPDATE ads SET {', '.join(update_fields)} WHERE id = %s"
            
            cursor.execute(sql, tuple(params))
            connection.commit()
            return {"success": True, "message": "Ad updated successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# ❌ 5. Delete Ad
@router.delete("/ads/{ad_id}")
def delete_ad(ad_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM ads WHERE id = %s", (ad_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Ad not found")

            cursor.execute("DELETE FROM ads WHERE id = %s", (ad_id,))
            connection.commit()
            return {"success": True, "message": "Ad deleted successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()