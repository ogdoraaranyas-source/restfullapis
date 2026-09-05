import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import pymysql

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

# Request validation models
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

# 📥 1. Create Product (with auto-generated display_id)
@router.post("/products")
def create_product(product_data: ProductCreate):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if category exists
            cursor.execute("SELECT id FROM categories WHERE id = %s", (product_data.category_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail="Category not found")

            # ✅ Get the MAX display_id from the table
            cursor.execute("SELECT COALESCE(MAX(display_id), 0) FROM products")
            max_display_id = cursor.fetchone()[0]
            new_display_id = max_display_id + 1  # Next sequential number (1, 2, 3...)

            # ✅ Insert with display_id
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
            
            return {"success": True, "message": "Product created successfully!", "product_id": product_id, "display_id": new_display_id}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# 👥 2. Get All Products (with display_id)
@router.get("/products")
def get_all_products():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT p.display_id, p.id, p.category_id, c.name as category_name, p.name, p.description, 
                       p.price, p.stock, p.img_url, p.status, p.created_at, p.updated_at
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                ORDER BY p.display_id ASC
            """
            cursor.execute(sql)
            products = cursor.fetchall()
            
            for product in products:
                for key in ['created_at', 'updated_at']:
                    if product.get(key) and isinstance(product[key], datetime):
                        product[key] = product[key].strftime('%Y-%m-%d %H:%M:%S')
                    
        return {"success": True, "products": products}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# 🔍 3. Get Single Product (with display_id)
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
            
            for key in ['created_at', 'updated_at']:
                if product.get(key) and isinstance(product[key], datetime):
                    product[key] = product[key].strftime('%Y-%m-%d %H:%M:%S')
                    
        return {"success": True, "product": product}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# 📝 4. Update Product
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
            return {"success": True, "message": "Product updated successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()

# ❌ 5. Delete Product
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
            return {"success": True, "message": "Product deleted successfully!"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database failure: {str(e)}")
    finally:
        connection.close()