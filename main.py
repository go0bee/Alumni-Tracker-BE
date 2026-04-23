import asyncio
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import models
import db
import scrapper
from import_excel import router as import_router
# from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI(title="Sistem Pelacakan Alumni Publik")
app.include_router(import_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    # allow_origins=[
    #     "http://localhost:5173",
    #     "https://alumni-tracker-feprod.up.railway.app",
    #     "https://tracker-alumni.up.railway.app"
    # ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Inisialisasi Database
models.Base.metadata.create_all(bind=db.engine)

# 3. Schema untuk Request Body
class AlumniCreate(BaseModel):
    nama: str
    keywords: str

class EvidenceCreate(BaseModel):
    source_name: str
    raw_data_url: str
    snippet_content: str
    extracted_score: float

# --- ENDPOINTS ---
# @app.middleware("http")
# async def fix_https_proxy(request, call_next):
#     # Cek header dari Railway proxy
#     proto = request.headers.get("x-forwarded-proto")
#     if proto == "https":
#         # Paksa scheme request menjadi https agar tidak terjadi redirect ke http
#         request.scope["scheme"] = "https"
#     return await call_next(request)

@app.post("/targets/")
def create_target(data: AlumniCreate, db_session: Session = Depends(db.get_db)):
    """
    Implementasi #1. Inisialisasi Profil (Admin Task) [cite: 16]
    """
    # Logika buat variasi nama sederhana [cite: 17, 18]
    nama_split = data.nama.split()
    if len(nama_split) > 1:
        variasi = f"{data.nama}, {nama_split[0][0]}. {' '.join(nama_split[1:])}"
    else:
        variasi = data.nama
    
    new_target = models.AlumniTarget(
        nama_asli=data.nama,
        variasi_nama=variasi,
        keywords=data.keywords, # [cite: 19]
        status="UNTRACKED", # Status awal sesuai rancangan [cite: 20]
        confidence_score=0.0
    )
    db_session.add(new_target)
    db_session.commit()
    db_session.refresh(new_target)
    return {"message": "Profil alumni berhasil disiapkan", "data": new_target}

@app.get("/all-alumni")
def get_all_alumni(db_session: Session = Depends(db.get_db)):

    return db_session.query(models.Alumni).all()

@app.get("/targets/")
def get_all_targets(db_session: Session = Depends(db.get_db)):
    """Mengambil semua daftar alumni untuk dashboard admin"""
    return db_session.query(models.AlumniTarget).all()

@app.put("/targets/{target_id}")
def update_target(target_id: int, data: AlumniCreate, db_session: Session = Depends(db.get_db)):
    target = db_session.query(models.AlumniTarget).filter(models.AlumniTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Alumni tidak ditemukan")

    target.nama = data.nama
    target.keywords = data.keywords
    nama_split = data.nama.split()
    if len(nama_split) > 1:
        target.variasi_nama = f"{data.nama}, {nama_split[0][0]}. {' '.join(nama_split[1:])}"
    else:
        target.variasi_nama = data.nama

    db_session.commit()
    db_session.refresh(target)
    return {"message": "Alumni berhasil diperbarui", "data": target}

@app.delete("/targets/{target_id}")
def delete_target(target_id: int, db_session: Session = Depends(db.get_db)):
    target = db_session.query(models.AlumniTarget).filter(models.AlumniTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Alumni tidak ditemukan")

    db_session.query(models.TrackingEvidence).filter(models.TrackingEvidence.target_id == target_id).delete()
    db_session.delete(target)
    db_session.commit()
    return {"message": "Alumni dan bukti terkait berhasil dihapus"}

@app.get("/track/{target_id}")
async def run_tracking(target_id: int, db_session: Session = Depends(db.get_db)):
    target = db_session.query(models.Alumni).filter(models.Alumni.id == target_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="Alumni tidak ditemukan")

    if target.is_tracked:
        return {"message": "Alumni sudah pernah ditrack", "id": target.id}

    scraper_output = await scrapper.run_scraper_logic(target.id, target.nama)

    track_results = scraper_output.get("data", [])

    if track_results:
        new_tracking_result = models.AlumniTrackingResult(target_id=target.id)

        for res in track_results:
            link = res.get("link", "").lower()

            if "linkedin.com" in link:
                new_tracking_result.link_linkedin = res["link"]

                rich_data = res.get("rich_data", [])
                posisi, tempat, alamat = parse_linkedin_rich_data(rich_data)

                new_tracking_result.posisi_kerja = posisi
                new_tracking_result.tempat_kerja = tempat
                new_tracking_result.alamat_kerja = alamat

            elif "instagram.com" in link:
                new_tracking_result.link_instagram = res["link"]

            elif "facebook.com" in link:
                new_tracking_result.link_facebook = res["link"]

            elif "tiktok.com" in link:
                new_tracking_result.link_tiktok = res["link"]

        db_session.add(new_tracking_result)

    target.is_tracked = True

    db_session.commit()
    db_session.refresh(target)

    return {
        "status": "success",
        "detail": {
            "top_results": scraper_output.get("data"),
            "best_match": scraper_output.get("best_match")
        }
    }

@app.post("/track-all")
async def run_tracking_all(db_session: Session = Depends(db.get_db)):
    targets = db_session.query(models.Alumni).filter(models.Alumni.is_tracked == False).all()

    if not targets:
        return {"message": "Tidak ada data alumni untuk di-track"}

    sem = asyncio.Semaphore(5)

    async def track_individual(target):
        async with sem:
            try:
                scraper_output = await scrapper.run_scraper_logic(
                    target.id,
                    target.nama,
                )

                target.is_tracked = True

                track_results = scraper_output.get("data", [])

                tracking_entry = models.AlumniTrackingResult(
                    target_id=target.id
                )

                for res in track_results:
                    link = res.get("link", "").lower()

                    if "linkedin.com" in link:
                        tracking_entry.link_linkedin = res["link"]

                        rich_data = res.get("rich_data", [])
                        posisi, tempat, alamat = parse_linkedin_rich_data(rich_data)

                        tracking_entry.posisi_kerja = posisi
                        tracking_entry.tempat_kerja = tempat
                        tracking_entry.alamat_kerja = alamat

                    elif "instagram.com" in link:
                        tracking_entry.link_instagram = res["link"]

                    elif "facebook.com" in link:
                        tracking_entry.link_facebook = res["link"]

                    elif "tiktok.com" in link:
                        tracking_entry.link_tiktok = res["link"]

                db_session.add(tracking_entry)
                print("\n--- Tracking Result ---")
                print(f"Alumni: {target.nama}")

                return {"id": target.id, "status": "processed"}

            except Exception as e:
                return {"id": target.id, "status": f"failed: {str(e)}"}

    tasks = [track_individual(t) for t in targets]
    results_summary = await asyncio.gather(*tasks)

    db_session.commit()

    return {
        "status": "batch_process_completed",
        "total": len(targets),
        "summary": results_summary
    }

def parse_linkedin_rich_data(rich_data: list):
    posisi = None
    tempat = None
    alamat = None

    if isinstance(rich_data, list):
        if len(rich_data) > 0:
            alamat = rich_data[0]
        if len(rich_data) > 1:
            posisi = rich_data[1]
        if len(rich_data) > 2:
            tempat = rich_data[2]

    return posisi, tempat, alamat

# @app.get("/track/{target_id}")
# async def run_tracking(target_id: int, db_session: Session = Depends(db.get_db)):
#     """
#     Implementasi #2, #3, & #4. Eksekusi & Logic Core [cite: 22, 29, 36]
#     """
#     target = db_session.query(models.AlumniTarget).filter(models.AlumniTarget.id == target_id).first()
    
#     if not target:
#         raise HTTPException(status_code=404, detail="Alumni tidak ditemukan")
    
#     # Jalankan Scraper (Fetching & Scoring)
#     result = await scrapper.run_scraper_logic(target.id, target.nama_asli, target.keywords)
    
#     # Update data alumni 
#     target.status = result['status']
#     target.confidence_score = result['score']
#     target.last_run = datetime.now()
    
#     # Simpan bukti pencarian untuk setiap hasil top candidates
#     track_results = result.get('data', [])
#     if track_results:
#         for res in track_results:
#             result = models.AlumniTrackingResult(
#                 target_id=target.id,
#                 link_instagram=res['link'] if 'instagram.com' in res['link'] else None,
#                 link_linkedin=res['link'] if 'linkedin.com' in res['link'] else None,
#                 link_facebook=res['link'] if 'facebook.com' in res['link'] else None,
#                 link_tiktok=res['link'] if 'tiktok.com' in res['link'] else None,
#                 best_match_title=res['title'],
#                 best_match_snippet=res['snippet'],
#                 best_match_link=res['link'],
#                 confidence_score=res['score']
#             )
#             db_session.add(result)

#     # candidates = result.get('data', [])
#     # if candidates:
#     #     for candidate in candidates:
#     #         evidence = models.TrackingEvidence(
#     #             target_id=target.id,
#     #             source_name="Public Web Search",
#     #             raw_data_url=candidate.get('link'),
#     #             snippet_content=candidate.get('snippet'),
#     #             extracted_score=candidate.get('score', 0.0)
#     #         )
#     #         db_session.add(evidence)
    
#     # db_session.commit()
#     # db_session.refresh(target)
    
#     return {
#         "status": "success",
#         "current_status": target.status,
#         "score": target.confidence_score,
#         "detail": {
#             # "top_results": candidates,
#             "top_results": result,
#             "best_match": result.get('best_match')
#         }
#     }

@app.get("/evidence/{target_id}")
def get_evidence(target_id: int, db_session: Session = Depends(db.get_db)):
    """Mengambil bukti temuan untuk verifikasi manual [cite: 47]"""
    return db_session.query(models.TrackingEvidence).filter(models.TrackingEvidence.target_id == target_id).all()

@app.post("/evidence/{target_id}")
def create_evidence(target_id: int, data: EvidenceCreate, db_session: Session = Depends(db.get_db)):
    """Menambahkan bukti temuan secara manual"""
    target = db_session.query(models.AlumniTarget).filter(models.AlumniTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Alumni tidak ditemukan")
    
    new_evidence = models.TrackingEvidence(
        target_id=target_id,
        source_name=data.source_name,
        raw_data_url=data.raw_data_url,
        snippet_content=data.snippet_content,
        extracted_score=data.extracted_score
    )
    db_session.add(new_evidence)
    
    # Update score alumni jika score baru lebih tinggi
    if data.extracted_score > target.confidence_score:
        target.confidence_score = data.extracted_score
        # Update status jika perlu
        if target.confidence_score > 0.8:
            target.status = "IDENTIFIED"
        elif target.confidence_score > 0.4:
            target.status = "MANUAL_VERIFICATION_REQUIRED"
    
    db_session.commit()
    db_session.refresh(new_evidence)
    return {"message": "Bukti berhasil ditambahkan", "data": new_evidence}

@app.delete("/evidence/{evidence_id}")
def delete_evidence(evidence_id: int, db_session: Session = Depends(db.get_db)):
    """Menghapus bukti temuan dan memperbarui score alumni"""
    evidence = db_session.query(models.TrackingEvidence).filter(models.TrackingEvidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Bukti tidak ditemukan")
    
    target_id = evidence.target_id
    db_session.delete(evidence)
    db_session.commit()
    
    # Recalculate target score based on remaining evidence
    target = db_session.query(models.AlumniTarget).filter(models.AlumniTarget.id == target_id).first()
    if target:
        remaining_evidence = db_session.query(models.TrackingEvidence).filter(models.TrackingEvidence.target_id == target_id).all()
        if remaining_evidence:
            max_score = max(e.extracted_score for e in remaining_evidence)
        else:
            max_score = 0.0
            
        target.confidence_score = max_score
        
        # Update status
        if target.confidence_score > 0.8:
            target.status = "IDENTIFIED"
        elif target.confidence_score > 0.4:
            target.status = "MANUAL_VERIFICATION_REQUIRED"
        else:
            target.status = "UNTRACKED"
            
        db_session.commit()
        
    return {"message": "Bukti berhasil dihapus"}

@app.post("/track/start")
async def start_tracking_all(db_session: Session = Depends(db.get_db)):
    """
    Menjalankan tracking otomatis untuk semua alumni_targets.
    Ini cocok setelah import Excel atau input massal.
    """

    targets = db_session.query(models.AlumniTarget).all()

    if not targets:
        raise HTTPException(status_code=404, detail="Tidak ada target alumni")

    tracked = 0
    updated = 0

    for target in targets:
        # jalankan scraper untuk setiap target
        result = await scrapper.run_scraper_logic(
            target.id,
            target.nama_asli,
            target.keywords
        )

        target.status = result["status"]
        target.confidence_score = result["score"]
        target.last_run = datetime.now()

        candidates = result.get("data", [])
        if candidates:
            for candidate in candidates:
                evidence = models.TrackingEvidence(
                    target_id=target.id,
                    source_name="Social Media Search",
                    raw_data_url=candidate.get("link"),
                    snippet_content=candidate.get("snippet"),
                    extracted_score=candidate.get("score", 0.0)
                )
                db_session.add(evidence)

        tracked += 1
        updated += len(candidates)

    db_session.commit()

    return {
        "message": "Tracking semua alumni selesai",
        "total_targets": len(targets),
        "tracked": tracked,
        "total_evidence_added": updated
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)