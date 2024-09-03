from fastapi import FastAPI, HTTPException
import pymysql
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import pymysql
app = FastAPI()

load_dotenv()

# Access the credentials
host = os.getenv("DB_HOST")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
database = os.getenv("DB_NAME")

# Connect to the database



def get_db():
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4"
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
def read_root(param: str, param2: str, args: str):
    conn, cur = get_db()
    try:
        # Constructing the query dynamically
        query = f"SELECT {param} FROM members WHERE {param2} = %s"
        print(args)
        cur.execute(query, (args,))
        result = cur.fetchone()
        if result:
            return {"message": f"Result: {result[0]}"}
        else:
            raise HTTPException(status_code=404, detail="Member not found")
    finally:
        cur.close()
        conn.close()

@app.get("/members/update_{param}/from_{param2}/{args}/{args2}")
def update_root(param: str, param2: str, args: str, args2: str):
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
def add_member(user_info: userInfo):
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



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)
