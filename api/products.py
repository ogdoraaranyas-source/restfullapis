import os
import threading
from datetime import datetime
from decimal import Decimal                          # ✅ Added
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import pymysql

from api.cache_helper import purge_vercel_cache

router = APIRouter(tags=["Products Management"])


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


def purge_async(paths):
    """Purge Vercel cache in a background thread (non-blocking)."""
    threading.Thread(
        target=purge_vercel_cache,
        args=(paths,),
        daemon=True
    ).start()


# ✅ NEW: Convert DB row to JSON-safe dict
def clean_row(row: dict) -> dict:
    clean = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            clean[key] = float(value)
        elif isinstance(value, datetime):
            clean[key] = value.strftime('%Y-%m-%d %H:%M:%S')
        else:
            clean[key] = value
    return clean


class ProductCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    img_url: Optional[str] = None
    status: str = "active"


class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    img_url: Optional[str] = None
    status: Optional[str] = None


# ================================
# 1. POST /products
# ================================
@router.post("/products")
def create_product(product_data: ProductCreate):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM categories WHERE id = %s", (product_data.category_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail="Category not found")

            cursor.execute("SELECT COALESCE(MAX(display_id), 0) FROM products")
            max_display_id = cursor.fetchone()[0]
            new_display_id = max_display_id + 1

            sql = """
                INSERT INTO products (display_id, category_id, name, description, price, stock, img_url, status, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """
            cursor.execute(sql, (
                new_display_id, product_data.category_id, product_data.name, product_data.description,
                product_data.price, product_data.stock, product_data.img_url,
                product_data.status
            ))
            connection.commit()
            product_id = cursor.lastrowid

        purge_async(["/api/products/top", "/api/products", "/api/categories"])

        return {
            "success": True,
            "message": "Product created successfully!",
            "product_id": product_id,
            "display_id": new_display_id
        }
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()


# ================================
# 2. GET /products
# ================================
@router.get("/products")
def get_all_products(
    category_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            if category_id is not None:
                print(f"🔍 Filtering by category_id={category_id}")
                cursor.execute("""
                    SELECT p.display_id, p.id, p.category_id, c.name as category_name,
                           p.name, SUBSTRING(p.description, 1, 150) as description,
                           p.price, p.stock, p.img_url, p.status, p.created_at, p.updated_at
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    WHERE p.category_id = %s AND p.status = 'active'
                    ORDER BY p.display_id ASC
                    LIMIT %s OFFSET %s
                """, (category_id, limit, offset))
            else:
                print(f"🔍 No filter — returning all products")
                cursor.execute("""
                    SELECT p.display_id, p.id, p.category_id, c.name as category_name,
                           p.name, SUBSTRING(p.description, 1, 150) as description,
                           p.price, p.stock, p.img_url, p.status, p.created_at, p.updated_at
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    ORDER BY p.display_id ASC
                    LIMIT %s OFFSET %s
                """, (limit, offset))

            products = cursor.fetchall()
            products = [clean_row(p) for p in products]

        # ✅ NO CACHE — always fresh for filter queries
        return JSONResponse(
            content={
                "success": True,
                "products": products,
                "count": len(products),
                "filtered_by_category": category_id,
            },
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
            }
        )
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# ================================
# 3. GET /products/top  (BEFORE /{product_id})
# ================================
@router.get("/products/top")
def get_top_products(limit: int = Query(5, ge=1, le=20)):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, name, thumbnail_url, created_at
                FROM categories
                ORDER BY id DESC
            """)
            categories = cursor.fetchall()

            for cat in categories:
                cursor.execute("""
                    SELECT 
                        p.display_id, p.id, p.category_id,
                        p.name, 
                        SUBSTRING(p.description, 1, 150) as description,
                        p.price, p.stock, p.img_url, p.status,
                        p.created_at, p.updated_at
                    FROM products p
                    WHERE p.category_id = %s AND p.status = 'active'
                    ORDER BY p.display_id ASC
                    LIMIT %s
                """, (cat['id'], limit))
                products = cursor.fetchall()

                # ✅ Convert each product row
                cat['products'] = [clean_row(p) for p in products]

                # ✅ Convert category row
                cat_clean = clean_row(cat)
                cat.update(cat_clean)

        return JSONResponse(
            content={
                "success": True,
                "limit_per_category": limit,
                "total_categories": len(categories),
                "dashboard": categories
            },
            headers={
                "Cache-Control": "public, s-maxage=300, stale-while-revalidate=86400",
            }
        )
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()


# ================================
# 4. GET /products/{product_id}
# ================================
@router.get("/products/{product_id}")
def get_product(product_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT p.display_id, p.id, p.category_id, c.name as category_name, p.name, p.description, 
                       p.price, p.stock, p.img_url, p.status, p.created_at, p.updated_at
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id = %s
            """
            cursor.execute(sql, (product_id,))
            product = cursor.fetchone()

            if not product:
                raise HTTPException(status_code=404, detail="Product not found")

            product = clean_row(product)

        return {"success": True, "product": product}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()


# ================================
# 5. PUT /products/{product_id}
# ================================
@router.put("/products/{product_id}")
def update_product(product_id: int, product_data: ProductUpdate):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Product not found")

            update_fields = []
            params = []

            if product_data.category_id is not None:
                update_fields.append("category_id = %s")
                params.append(product_data.category_id)
            if product_data.name is not None:
                update_fields.append("name = %s")
                params.append(product_data.name)
            if product_data.description is not None:
                update_fields.append("description = %s")
                params.append(product_data.description)
            if product_data.price is not None:
                update_fields.append("price = %s")
                params.append(product_data.price)
            if product_data.stock is not None:
                update_fields.append("stock = %s")
                params.append(product_data.stock)
            if product_data.img_url is not None:
                update_fields.append("img_url = %s")
                params.append(product_data.img_url)
            if product_data.status is not None:
                update_fields.append("status = %s")
                params.append(product_data.status)

            if not update_fields:
                return {"success": True, "message": "No modification parameters specified."}

            params.append(product_id)
            sql = f"UPDATE products SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = %s"

            cursor.execute(sql, tuple(params))
            connection.commit()

        purge_async(["/api/products/top", "/api/products", "/api/categories"])

        return {"success": True, "message": "Product updated successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()


# ================================
# 6. DELETE /products/{product_id}
# ================================
@router.delete("/products/{product_id}")
def delete_product(product_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Product not found")

            cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
            connection.commit()

        purge_async(["/api/products/top", "/api/products", "/api/categories"])

        return {"success": True, "message": "Product deleted successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()


# ================================
# ✅ GET /search — Global search with TiDB Full-Text
# ================================
# ================================
# ✅ GET /search — Global search with LIKE
# ================================
@router.get("/search")
def global_search(
    q: str = Query("", min_length=0, max_length=50),
    limit: int = Query(30, ge=1, le=100),
):
    if not q or len(q.strip()) == 0:
        return {"success": True, "categories": [], "products": []}

    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            search_term = f"%{q.strip()}%"

            # ✅ 1. Search categories with LIKE
            cursor.execute("""
                SELECT id, name, thumbnail_url, created_at
                FROM categories
                WHERE name LIKE %s
                ORDER BY id DESC
                LIMIT 10
            """, (search_term,))
            categories = cursor.fetchall()
            for cat in categories:
                if cat.get('created_at') and isinstance(cat['created_at'], datetime):
                    cat['created_at'] = cat['created_at'].strftime('%Y-%m-%d %H:%M:%S')

            # ✅ 2. Search products with LIKE ONLY
            cursor.execute("""
                SELECT p.display_id, p.id, p.category_id, c.name as category_name,
                       p.name, SUBSTRING(p.description, 1, 150) as description,
                       p.price, p.stock, p.img_url, p.status, p.created_at, p.updated_at
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.status = 'active' AND (
                    p.name LIKE %s OR
                    c.name LIKE %s
                )
                ORDER BY p.display_id ASC
                LIMIT %s
            """, (search_term, search_term, limit))
            products = cursor.fetchall()
            products = [clean_row(p) for p in products]

        return JSONResponse(
            content={
                "success": True,
                "query": q,
                "categories": categories,
                "products": products,
                "count": len(products),
            },
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
            }
        )
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()