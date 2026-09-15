import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pymysql

from api.cache_helper import purge_vercel_cache   # ✅ Import purge helper

router = APIRouter(tags=["Categories Management"])


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


class CategoryCreate(BaseModel):
    name: str
    thumbnail_url: str


class CategoryUpdate(BaseModel):
    name: str | None = None
    thumbnail_url: str | None = None


# ================================
# 📥 1. Create Category — Purges cache
# ================================
@router.post("/categories")
def set_category(cat_data: CategoryCreate):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Prevent duplicate category strings
            cursor.execute("SELECT id FROM categories WHERE name = %s", (cat_data.name,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Category name already exists.")

            sql = "INSERT INTO categories (name, thumbnail_url, created_at) VALUES (%s, %s, NOW())"
            cursor.execute(sql, (cat_data.name, cat_data.thumbnail_url))
            connection.commit()

        # ✅ Purge Vercel CDN cache
        purge_vercel_cache(["/api/categories", "/api/products/top"])

        return {"success": True, "message": "Category created successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()


# ================================
# 👥 2. Get All Categories — Cached
# ================================
@router.get("/categories")
def get_all_category():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SELECT id, name, thumbnail_url, created_at FROM categories ORDER BY id DESC"
            cursor.execute(sql)
            categories = cursor.fetchall()

            for cat in categories:
                if cat.get('created_at') and isinstance(cat['created_at'], datetime):
                    cat['created_at'] = cat['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        return JSONResponse(
            content={"success": True, "categories": categories},
            headers={
                "Cache-Control": "public, s-maxage=300, stale-while-revalidate=86400",
            }
        )
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    finally:
        connection.close()


# ================================
# 📝 3. Edit Category — Purges cache
# ================================
@router.put("/categories/{category_id}")
def edit_category(category_id: int, cat_data: CategoryUpdate):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")

            update_fields = []
            params = []

            if cat_data.name is not None:
                update_fields.append("name = %s")
                params.append(cat_data.name)
            if cat_data.thumbnail_url is not None:
                update_fields.append("thumbnail_url = %s")
                params.append(cat_data.thumbnail_url)

            if not update_fields:
                return {"success": True, "message": "No modification parameters specified."}

            params.append(category_id)
            sql = f"UPDATE categories SET {', '.join(update_fields)} WHERE id = %s"

            cursor.execute(sql, tuple(params))
            connection.commit()

        # ✅ Purge Vercel CDN cache
        purge_vercel_cache(["/api/categories", "/api/products/top"])

        return {"success": True, "message": "Category updated successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()


# ================================
# ❌ 4. Delete Category — Purges cache
# ================================
@router.delete("/categories/{category_id}")
def delete_category(category_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Category record not found")

            cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
            connection.commit()

        # ✅ Purge Vercel CDN cache
        purge_vercel_cache(["/api/categories", "/api/products/top"])

        return {"success": True, "message": "Category deleted successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()