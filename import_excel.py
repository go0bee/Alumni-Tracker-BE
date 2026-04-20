from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

import db
import models

router = APIRouter(prefix="/admin", tags=["Admin Import Excel"])

REQUIRED_COLUMNS = [
    "Nama Lulusan",
    "NIM",
    "Tahun Masuk",
    "Tanggal Lulus",
    "Fakultas",
    "Program Studi"
]

@router.post("/import-excel")
async def import_excel_alumni(
    file: UploadFile = File(...),
    db_session: Session = Depends(db.get_db)
):
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="File harus format .xlsx")

    try:
        df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file Excel: {str(e)}")

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise HTTPException(status_code=400, detail=f"Kolom Excel kurang: {missing_cols}")

    inserted = 0
    skipped = 0

    seen_nims = set()

    for _, row in df.iterrows():
        if pd.isna(row["NIM"]) or pd.isna(row["Nama Lulusan"]):
            skipped += 1
            continue

        nim = str(row["NIM"]).strip()
        nama = str(row["Nama Lulusan"]).strip()

        if not nim or not nama:
            skipped += 1
            continue

        # skip duplicate dalam file excel yang sama
        if nim in seen_nims:
            skipped += 1
            continue
        seen_nims.add(nim)

        # skip duplicate yang sudah ada di DB
        existing = db_session.query(models.Alumni).filter(models.Alumni.nim == nim).first()
        if existing:
            skipped += 1
            continue

        alumni = models.Alumni(
            nim=nim,
            nama=nama,
            tahun_masuk=int(row["Tahun Masuk"]) if pd.notna(row["Tahun Masuk"]) else None,
            tanggal_lulus=str(row["Tanggal Lulus"]).strip() if pd.notna(row["Tanggal Lulus"]) else None,
            fakultas=str(row["Fakultas"]).strip() if pd.notna(row["Fakultas"]) else None,
            program_studi=str(row["Program Studi"]).strip() if pd.notna(row["Program Studi"]) else None
        )

        db_session.add(alumni)
        inserted += 1

    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal commit DB: {str(e)}")

    return {
        "message": "Import selesai",
        "inserted": inserted,
        "skipped": skipped,
        "total_rows": len(df)
    }