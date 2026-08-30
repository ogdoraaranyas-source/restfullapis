import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import pymysql

# 1. Initialize FastAPI
app = FastAPI(title="E-Commerce Identity Engine")

# 2. Configure CORS so Flutter can communicate safely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#q0f0ECHvJJRZEZoq
# 3. Secure TiDB Connection Pool Helper
def get_db_connection():
    try:
        return pymysql.connect(
            host=os.getenv("TIDB_HOST"),
            user=os.getenv("TIDB_USER"),
            password=os.getenv("TIDB_PASSWORD"),
            database=os.getenv("TIDB_DB"),
            port=4000,
            ssl={"ssl_p豐富": True} # Enforces modern security protocols over serverless hops
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# 4. Pydantic Schema Model for SaveUser Input Validation
class UserSignUp(BaseModel):
    name: str
    email: EmailStr  # Automatically rejects malformed emails (e.g., missing '@' or '.com')
    password: str

#--- ENDPOINTS ---

# 👤 API Route 1: Save User (POST)
@app.post("/api/users")
def save_user(user_data: UserSignUp):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if user already exists to prevent duplicate entries
            cursor.execute("SELECT id FROM users WHERE email = %s", (user_data.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered in system")

            # Write the new profile record directly to TiDB
            sql = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_data.name, user_data.email, user_data.password))
            connection.commit()
            
            return {"success": True, "message": "User saved successfully!"}
            
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database internal failure: {str(e)}")
    finally:
        connection.close()

# 👥 API Route 2: Get All Users (GET)
@app.get("/api/users")
def get_users():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Retrieve profiles while excluding password keys for security
            cursor.execute("SELECT id, name, email FROM users ORDER BY id DESC")
            users = cursor.fetchall()
            
        return {"success": True, "users": users}
        
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database internal failure: {str(e)}")
    finally:
        connection.close()
