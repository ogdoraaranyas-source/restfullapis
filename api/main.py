import os
from fastapi import FastAPI, HTTPException
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
            ssl={"ssl_disabled": False}  # Corrected character error to support secure hops
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# 4. Pydantic Schema Model for SaveUser Input Validation
class UserSignUp(BaseModel):
    name: str
    email: EmailStr  # Automatically rejects malformed emails (e.g., missing '@' or '.com')
    password: str

# --- ENDPOINTS ---

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



class UserLogin(BaseModel):
    # This matches the exact keys you are sending in your JSON payload
    phone_number: str 
    password_hash: str  

@app.post("/api/login")
def login_user(login_data: UserLogin):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. UPDATED: Fetch target record using 'phone_number' and select 'password_hash' 
            sql = "SELECT id, name, phone_number, password_hash FROM users WHERE phone_number = %s"
            cursor.execute(sql, (login_data.mobile,))
            user_record = cursor.fetchone()

            # 2. Check if the user record exists in the database framework
            if not user_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="User not found"
                )

            # 3. UPDATED: Verify passwords matching your password_hash layout string 
            # Note: If you are storing plain text under password_hash right now, keep line below.
            # If using bcrypt hashes, replace line with: if not pwd_context.verify(login_data.password, user_record["password_hash"]):
            if user_record["password_hash"] != login_data.password:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    detail="Invalid credentials. Incorrect password."
                )

            # 4. Successful authenticated payload configuration map
            return {
                "success": True,
                "message": "Login successful! Welcome to the Admin Portal Dashboard Hub.",
                "user": {
                    "id": user_record["id"],
                    "name": user_record["name"],
                    "phone_number": user_record["phone_number"]
                    # Stripped out returning password string assets for secure network communication
                }
            }
            
    except pymysql.MySQLError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Database internal operational failure: {str(e)}"
        )
    finally:
        connection.close()
