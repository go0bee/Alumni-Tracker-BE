from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from db import Base

class AlumniTarget(Base):
    __tablename__ = "alumni_targets"

    id = Column(Integer, primary_key=True, index=True)
    nama_asli = Column(String(100))
    variasi_nama = Column(Text)
    keywords = Column(String(255)) # Contoh: "UMM, Informatika" [cite: 19]
    status = Column(String(50), default="UNTRACKED") # [cite: 20]
    confidence_score = Column(Float, default=0.0, nullable=True)
    last_run = Column(DateTime, nullable=True)

class TrackingEvidence(Base):
    __tablename__ = "tracking_evidence"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(
        Integer,
        ForeignKey(AlumniTarget.id, ondelete="CASCADE")
        )
    source_name = Column(String(255))
    raw_data_url = Column(Text, nullable=True)
    snippet_content = Column(Text, nullable=True)
    extracted_score = Column(Float, default=0.0, nullable=True)

class Alumni(Base):
    __tablename__ = "alumni"

    id = Column(Integer, primary_key=True, index=True)
    nim = Column(String(50), unique=True, index=True, nullable=False)

    nama = Column(String(200), nullable=False)
    tahun_masuk = Column(Integer, nullable=True)
    tanggal_lulus = Column(String(50), nullable=True)  # biar fleksibel (excel kadang format aneh)
    fakultas = Column(String(200), nullable=True)
    program_studi = Column(String(200), nullable=True)
    is_tracked = Column(Boolean, default=False)

class AlumniTrackingResult(Base):
    __tablename__ = "alumni_tracking_results"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(
        Integer,
        ForeignKey(Alumni.id, ondelete="CASCADE")
        )
    link_instagram = Column(Text, nullable=True)
    link_linkedin = Column(Text, nullable=True)
    link_facebook = Column(Text, nullable=True)
    link_tiktok = Column(Text, nullable=True)
    tempat_kerja = Column(String(255), nullable=True)
    alamat_kerja = Column(String(255), nullable=True)
    posisi_kerja = Column(String(255), nullable=True)
    jenis_industri = Column(String(255), nullable=True)
    # best_match_title = Column(String(255))
    # best_match_snippet = Column(Text)
    # best_match_link = Column(Text)
    # confidence_score = Column(Float, default=0.0, nullable=True)