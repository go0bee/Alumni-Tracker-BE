import httpx
from bs4 import BeautifulSoup
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Gantilah dengan API Key gratis dari serpapi.com
SERP_API_KEY = os.getenv("SERP_API_KEY")

async def fetch_data(query):
    """
    Implementasi FUNCTION ExecuteMultiSourceTracking menggunakan Official API [cite: 29, 33]
    """
    results = []
    # Endpoint SerpApi untuk Google Search
    url = "https://serpapi.com/search.json"
    params = {
        "q": query,
        "api_key": SERP_API_KEY,
        "engine": "google",
        "hl": "id",
        "gl": "id"
    }
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                
                # Mengambil hasil pencarian organik
                organic_results = data.get("organic_results", [])
                # Ambil hingga 5 hasil teratas
                for item in organic_results[:5]:
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", "")
                    })
    except Exception as e:
        print(f"Error pada API: {e}")
        
    return results

def calculate_confidence(candidate_data, target_profile):
    """
    Implementasi FUNCTION ProcessResults & CalculateConfidence [cite: 36, 38]
    """
    score = 0.0
    title = candidate_data['title'].lower()
    snippet = candidate_data['snippet'].lower()
    nama_target = target_profile['nama'].lower()
    
    # 1. Cek Kemiripan Nama (Bobot 0.5) 
    if nama_target in title:
        score += 0.5
    
    # 2. Cek Afiliasi/Keywords (Bobot 0.4) [cite: 19]
    keywords = [kw.strip().lower() for kw in target_profile['keywords'].split(',')]
    for kw in keywords:
        if kw in snippet or kw in title:
            score += 0.4
            break # Cukup satu keyword yang cocok untuk menambah score afiliasi
            
    return min(score, 1.0)

async def run_scraper_logic(target_id, target_nama, target_keywords):
    """
    Fungsi utama yang menggabungkan Fetching dan Scoring [cite: 27, 35]
    """
    # 1. Split keywords and Generate Search Queries [cite: 26]
    keywords_list = [kw.strip() for kw in target_keywords.split(',')]
    
    all_raw_results = []
    seen_links = set()

    # 2. Fetch Data for each keyword [cite: 33]
    for kw in keywords_list:
        query = f'"{target_nama}" {kw}'
        keyword_results = await fetch_data(query)
        
        for res in keyword_results:
            if res['link'] not in seen_links:
                seen_links.add(res['link'])
                all_raw_results.append(res)
    
    scored_results = []
    target_profile = {"nama": target_nama, "keywords": target_keywords}

    for candidate in all_raw_results:
        score = calculate_confidence(candidate, target_profile)
        candidate_with_score = {
            "title": candidate.get("title", ""),
            "snippet": candidate.get("snippet", ""),
            "link": candidate.get("link", ""),
            "score": score
        }
        scored_results.append(candidate_with_score)

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    # Ambil 5 teratas dari gabungan hasil pencarian
    top_results = scored_results[:5]

    highest_score = top_results[0]["score"] if top_results else 0.0
    best_match = top_results[0] if top_results else {"title": "", "snippet": "Data tidak ditemukan", "link": "", "score": 0.0}

    status = "UNTRACKED"
    if highest_score > 0.8:
        status = "IDENTIFIED"
    elif highest_score > 0.4:
        status = "MANUAL_VERIFICATION_REQUIRED"

    return {
        "score": highest_score,
        "data": top_results,
        "best_match": best_match,
        "status": status
    }