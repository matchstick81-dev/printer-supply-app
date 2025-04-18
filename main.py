from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import datetime
import base64
import os
import json
import openpyxl
import pandas as pd

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_form():
    return FileResponse("static/form.html")

@app.get("/admin", response_class=HTMLResponse)
def serve_admin():
    with open("static/admin.html", encoding="utf-8") as f:
        return f.read()

# 소모품 목록 불러오기
CONSUMABLES_DB = "data/consumables.xlsx"

def load_consumables():
    result = []
    wb = openpyxl.load_workbook(CONSUMABLES_DB)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        category, brand, name = row
        if category and brand and name:
            result.append({"category": category, "brand": brand, "name": name})
    return result

@app.get("/api/categories")
def get_categories():
    items = load_consumables()
    return sorted(set(i["category"] for i in items))

@app.get("/api/brands")
def get_brands():
    items = load_consumables()
    return sorted(set(i["brand"] for i in items))

@app.get("/api/items")
def get_items(category: str, brand: str):
    items = load_consumables()
    return [i["name"] for i in items if i["category"] == category and i["brand"] == brand]

# 데이터 모델
class Item(BaseModel):
    item: str
    qty: int

class SubmitData(BaseModel):
    projectNumber: str
    printerModel: str
    department: str
    team: str
    userName: str
    items: List[Item]
    signature: str

@app.post("/api/save")
def save_data(data: SubmitData):
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("signatures", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    img_data = data.signature.split(",")[1]
    img_path = f"signatures/sign_{now}.png"
    with open(img_path, "wb") as f:
        f.write(base64.b64decode(img_data))

    record = data.dict()
    record["savedAt"] = now
    record["signaturePath"] = img_path
    with open(f"data/data_{now}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "saved": now}

@app.get("/api/logs")
def get_logs(
    keyword: str = Query("", alias="q"),
    start: str = Query("", alias="start"),
    end: str = Query("", alias="end")
):
    logs = []
    for file in sorted(os.listdir("data")):
        if file.endswith(".json"):
            with open(f"data/{file}", encoding="utf-8") as f:
                entry = json.load(f)
                entry["signaturePath"] = "/" + entry["signaturePath"].replace("\\", "/")
                logs.append(entry)

    if keyword:
        logs = [e for e in logs if keyword in e["projectNumber"] or keyword in e["printerModel"] or keyword in e["userName"]]

    if start:
        logs = [e for e in logs if e["savedAt"] >= start.replace("-", "")]
    if end:
        logs = [e for e in logs if e["savedAt"] <= end.replace("-", "")]

    return logs

@app.get("/api/download")
def download_excel():
    logs = []
    for file in sorted(os.listdir("data")):
        if file.endswith(".json"):
            with open(f"data/{file}", encoding="utf-8") as f:
                entry = json.load(f)
                for item in entry["items"]:
                    logs.append({
                        "날짜": entry["savedAt"],
                        "공사번호": entry["projectNumber"],
                        "프린터": entry["printerModel"],
                        "소모품": item["item"],
                        "수량": item["qty"],
                        "소속": entry["department"],
                        "부서": entry["team"],
                        "이름": entry["userName"],
                        "서명": entry["signaturePath"]
                    })

    df = pd.DataFrame(logs)
    path = "data/기록_다운로드.xlsx"
    df.to_excel(path, index=False)
    return FileResponse(path, filename="기록_다운로드.xlsx")
