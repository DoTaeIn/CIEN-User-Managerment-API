from imp import reload
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import pymysql
import jwt
app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

# Access the credentials
host = os.getenv("DB_HOST")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
database = os.getenv("DB_NAME")
port = os.getenv("DB_PORT")
secret = os.getenv("JWT_SECRET")

# Connect to the database
def get_db():
    conn = pymysql.connect(
        host="127.0.0.1",
        user=user,
        password=password,
        database=database,
        port=int(port),
        charset="utf8mb4",

    )
    cur = conn.cursor()
    return conn, cur

class userInfo(BaseModel):
    name: str
    university: int
    phonenum: str
    birthdate: datetime
    schoolid: int
    major: str
    activestatus : int

# Get member name w/ CIENid
@app.get("/members/get_{param}/from_{param2}/{args}")
def read_root(param: str, param2: str, args: str, token: str):
    if not checkTokenValidation(token):
        return {"message": "Invalid token"}
    conn, cur = get_db()
    new_token = jwt.encode({"CIENid": args}, secret, algorithm="HS256")
    try:
        # Constructing the query dynamically
        query = f"SELECT {param} FROM members WHERE {param2} = %s"
        print(args)
        cur.execute(query, (args,))
        result = cur.fetchone()
        if result:
            print(new_token)
            return {"message": f"Result: {result[0]}"}

        else:
            raise HTTPException(status_code=404, detail="Member not found")
    finally:
        cur.close()
        conn.close()

@app.get("/members/update_{param}/from_{param2}/{args}/{args2}")
def update_root(param: str, param2: str, args: str, args2: str, token: str):
    if not checkTokenValidation(token):
        return {"message": "Invalid token"}
    conn, cur = get_db()
    try:
        # Constructing the query dynamically
        query = f"UPDATE members SET {param} = %s WHERE {param2} = %s"
        cur.execute(query, (args, args2))
        conn.commit()
        return {"message": f"Updated {param} to {args} for {param2} {args2}"}
    finally:
        cur.close()
        conn.close()


@app.post("/members/add_by_name")
def add_member(user_info: userInfo, token: str):
    if not checkTokenValidation(token):
        return {"message": "Invalid token"}
    conn, cur = get_db()
    try:
        # Constructing the query dynamically and securely
        query = """
        INSERT INTO members (name, university, phonenum, birthdate, schoolid, major, activestatus)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (
            user_info.name,
            user_info.university,
            user_info.phonenum,
            user_info.birthdate,
            user_info.schoolid,
            user_info.major,
            user_info.activestatus
        ))
        conn.commit()
        return {"message": f"Added {user_info.name} to members"}
    except Exception as e:
        conn.rollback()  # Rollback in case of error
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()



@app.get("/members/is_insider/from_{param}/{args}")
def is_insider(param : str, args: str, token: str):
    if checkTokenValidation(token):
        conn, cur = get_db()
        try:
            query = f"SELECT university FROM members WHERE {param} = %s"
            cur.execute(query, (args,))
            result = cur.fetchone()
            if result:
                if (result[0] == 0):
                    return {"message": f" {args} is an insider"}
                elif (result[0] == 2 or result[0] == 1 or result[0] == 3):
                    print(jwt.decode(token, secret, algorithm="HS256"))
                    return {"message": f" {args} is not an insider"}
                else:
                    return {"message": f" {args} is not a member"}
            else:
                raise HTTPException(status_code=404, detail="Member not found")

        finally:
            cur.close()
            conn.close()
    else:
        return {"message": "Invalid token"}


def checkTokenValidation(token):
    try:
        result = jwt.decode(token, secret, algorithms=["HS256"])
        exp_time = datetime.fromtimestamp(result["exp"])  # Convert exp timestamp to datetime

        if exp_time < datetime.now():  # If expired
            return False
        return True  # Token is still valid
    except jwt.ExpiredSignatureError:
        return False  # Token is expired
    except jwt.InvalidTokenError:
        return False  # Invalid token


@app.get("/login")
def login(id: str, password: str):
    conn, cur = get_db()
    try:
        # Fetch failed attempts and lock time
        query = "SELECT failed_attempts, locked_until FROM Logininfo WHERE username = %s"
        cur.execute(query, (id,))
        user = cur.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Member not found")

        failed_attempts = user[0]
        locked_until = user[1]

        # Check if account is locked
        if locked_until and locked_until > datetime.now():
            remaining_time = (locked_until - datetime.now()).seconds
            raise HTTPException(status_code=403, detail=f"Account locked. Try again in {remaining_time} seconds.")

        # Decrypt password from DB
        query = """
        SELECT CONVERT(AES_DECRYPT(UNHEX(password), %s) USING utf8) AS decrypted_password 
        FROM Logininfo WHERE username = %s
        """
        cur.execute(query, (secret, id))
        result = cur.fetchone()

        if result and result[0]:
            if password == result[0]:
                # Reset failed attempts on successful login
                query = "UPDATE Logininfo SET failed_attempts = 0, locked_until = NULL WHERE username = %s"
                cur.execute(query, (id,))
                conn.commit()

                # Generate JWT token
                expires = datetime.now() + timedelta(minutes=180)
                token = jwt.encode({"CIENid": id, "exp": expires.timestamp()}, secret, algorithm="HS256")
                return {"message": "Login successful", "token": token}
            else:
                # Incorrect password - Increment failed attempts
                failed_attempts += 1
                if failed_attempts >= 3:
                    lock_time = datetime.now() + timedelta(hours=1)  # Lock for 1 hour
                    query = "UPDATE Logininfo SET failed_attempts = %s, locked_until = %s WHERE username = %s"
                    cur.execute(query, (failed_attempts, lock_time, id))
                    conn.commit()
                    raise HTTPException(status_code=403, detail="Too many failed attempts. Account locked for 1 hour.")
                else:
                    query = "UPDATE Logininfo SET failed_attempts = %s WHERE username = %s"
                    cur.execute(query, (failed_attempts, id))
                    conn.commit()
                raise HTTPException(status_code=401, detail="Incorrect password")
        else:
            raise HTTPException(status_code=404, detail="Member not found")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000, reload=True)
