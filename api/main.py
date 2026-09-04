import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import pymysql

# 1. Initialize FastAPI (Must be named app for Vercel)
app = FastAPI(title="E-Commerce Identity Engine")

# 2. Configure CORS so Flutter can communicate safely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Secure TiDB Connection Pool Helper
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

# 4. Pydantic Schema Model updated to support full profile parameters on sign up
class UserSignUp(BaseModel):
    name: str
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    mobile: str | None = None
    role: str = "customer"  # Matches your fallback default role assignment state
    status: str = "pending_verification"  # Matches your default data validation status

# 5. Fixed Pydantic Schema Model for Login to use 'mobile' matching your database profile
class UserLogin(BaseModel):
    mobile: str 
    password: str  

# --- ENDPOINTS ---
 
# 👤 API Route 1: Save User (POST) - Mapped precisely to your updated schema grid
@app.post("/api/users")
def save_user(user_data: UserSignUp):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if email or mobile already exists to prevent duplication
            cursor.execute("SELECT id FROM users WHERE email = %s", (user_data.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered in system")
                
            if user_data.mobile:
                cursor.execute("SELECT id FROM users WHERE mobile = %s", (user_data.mobile,))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Mobile number already registered in system")

            # Writes comprehensive array criteria safely including timestamps
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

# 👥 API Route 2: Get All Users (GET) - Features exhaustive enterprise columns output
@app.get("/api/users")
def get_users():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Retrieves full record data metrics, sorting newest profiles first
            sql = """
                SELECT id, name, email, first_name, last_name, mobile, role, status, 
                       created_at, updated_at, email_verified_at, last_login_at 
                FROM users 
                ORDER BY id DESC
            """
            cursor.execute(sql)
            users = cursor.fetchall()
            
            # Format dates into clean text strings for JSON serialization stability
            for user in users:
                for key in ['created_at', 'updated_at', 'email_verified_at', 'last_login_at']:
                    if user[key] and isinstance(user[key], datetime):
                        user[key] = user[key].strftime('%Y-%m-%d %H:%M:%S')
            
        return {"success": True, "users": users}
        
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database internal failure: {str(e)}")
    finally:
        connection.close()

# 🔑 API Route 3: User Login (POST) - FULLY CORRELATED TO YOUR DATA COLUMNS
@app.post("/api/login")
def login_user(login_data: UserLogin):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Look up profiles targeting your 'mobile' column index
            sql = """
                SELECT id, name, email, password, first_name, last_name, mobile, role, status 
                FROM users 
                WHERE mobile = %s
            """
            cursor.execute(sql, (login_data.mobile,))
            user_record = cursor.fetchone()

            # Verify profile existence tracking
            if not user_record:
                return {
                    "success": False,
                    "message": "User not found"
                }

            # Direct lookup comparison matching your exact column data specifications
            if user_record["password"] != login_data.password:
                return {
                    "success": False,
                    "message": "Invalid credentials. Incorrect password."
                }

            # Programmatic logging utility: Record the current login timestamp string into TiDB
            update_sql = "UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s"
            cursor.execute(update_sql, (user_record["id"],))
            connection.commit()

            return {
                "success": True,
                "message": "Login successful! Welcome to the Admin Portal Dashboard Hub.",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Database internal operational failure: {str(e)}"
        )
    finally:
        connection.close()
