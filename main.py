from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator
from typing import List
from uuid import uuid4
import shutil
import os
from supabase import create_client, Client

# ---- Supabase Setup ----
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-or-service-role-key"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---- FastAPI App ----
app = FastAPI()

# ---- Directories ----
os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=".")

# ---- Pydantic Models ----
class Todo(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=500)
    completed: bool = False

    @validator("title")
    def not_blank_title(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be blank")
        return v

    @validator("description")
    def not_blank_desc(cls, v):
        if not v.strip():
            raise ValueError("Description cannot be blank")
        return v

class TodoOut(Todo):
    id: str
    file_path: str = ""

# ---- Routes ----

# Home page with form and list
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    todos = supabase.table("todos").select("*").execute().data
    return templates.TemplateResponse("index.html", {"request": request, "todos": todos})

# Create todo + upload file
@app.post("/todos", response_model=TodoOut)
async def create_todo(
    title: str = Form(...),
    description: str = Form(...),
    completed: bool = Form(False),
    file: UploadFile = File(...)
):
    todo_id = str(uuid4())
    filename = f"{todo_id}_{file.filename}"
    filepath = os.path.join("uploads", filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    record = {
        "id": todo_id,
        "title": title,
        "description": description,
        "completed": completed,
        "file_path": f"/uploads/{filename}"
    }

    result = supabase.table("todos").insert(record).execute()
    if result.error:
        raise HTTPException(status_code=500, detail=result.error.message)

    return record

# List todos as JSON
@app.get("/todos", response_model=List[TodoOut])
def list_todos():
    result = supabase.table("todos").select("*").execute()
    if result.error:
        raise HTTPException(status_code=500, detail=result.error.message)
    return result.data

# Stream media file
@app.get("/stream/{filename}")
def stream_file(filename: str):
    path = os.path.join("uploads", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
