from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
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