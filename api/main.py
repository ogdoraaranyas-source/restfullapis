import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import pymysql

# Import routers
from api.categories import router as categories_router
from api.uploadimage import router as upload_image_router

# Initialize FastAPI
app = FastAPI(title="E-Commerce Identity Engine")  # ✅ THIS IS THE 'app' VARIABLE!

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(categories_router, prefix="/api")
app.include_router(upload_image_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "API is working!", "status": "healthy"}

# Database connection helper
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
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# Pydantic models
class UserSignUp(BaseModel):
    name: str
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    mobile: str
    role: str = "customer"
    status: str = "pending_verification"

class UserLogin(BaseModel):
    mobile: str 
    password: str  

# User endpoints
@app.post("/api/users")
def save_user(user_data: UserSignUp):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if mobile already exists
            cursor.execute("SELECT id FROM users WHERE mobile = %s", (user_data.mobile,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Mobile number already registered in system")

            # Insert user
            sql = """
                INSERT INTO users 
                (name, email, password, first_name, last_name, mobile, role, status, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """
            cursor.execute(sql, (
                user_data.name, user_data.email, user_data.password,
                user_data.first_name, user_data.last_name, user_data.mobile,
                user_data.role, user_data.status
            ))
            connection.commit()
            
            return {"success": True, "message": "User saved successfully!"}
            
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database internal failure: {str(e)}")
    finally:
        connection.close()

@app.get("/api/users")
def get_users():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT id, name, email, password, first_name, last_name, mobile, role, status, 
                       created_at, updated_at, email_verified_at, last_login_at 
                FROM users 
                ORDER BY id DESC
            """
            cursor.execute(sql)
            users = cursor.fetchall()
            
            for user in users:
                for key in ['created_at', 'updated_at', 'email_verified_at', 'last_login_at']:
                    if user.get(key) and isinstance(user[key], datetime):
                        user[key] = user[key].strftime('%Y-%m-%d %H:%M:%S')
            
        return {"success": True, "users": users}
        
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database internal failure: {str(e)}")
    finally:
        connection.close()

@app.post("/api/login")
def login_user(login_data: UserLogin):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT id, name, email, password, first_name, last_name, mobile, role, status 
                FROM users 
                WHERE mobile = %s
            """
            cursor.execute(sql, (login_data.mobile,))
            user_record = cursor.fetchone()

            if not user_record:
                return {"success": False, "message": "User not found"}

            if user_record["password"] != login_data.password:
                return {"success": False, "message": "Invalid credentials. Incorrect password."}

            update_sql = "UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s"
            cursor.execute(update_sql, (user_record["id"],))
            connection.commit()

            return {
                "success": True,
                "message": "Login successful!",
                "user": {
                    "id": user_record["id"],
                    "name": user_record["name"],
                    "email": user_record["email"],
                    "first_name": user_record["first_name"],
                    "last_name": user_record["last_name"],
                    "mobile": user_record["mobile"],
                    "role": user_record["role"],
                    "status": user_record["status"]
                }
            }
            
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database internal operational failure: {str(e)}")
    finally:
        connection.close()