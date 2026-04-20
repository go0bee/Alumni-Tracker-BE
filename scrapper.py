import httpx
import os
from dotenv import load_dotenv

load_dotenv()

SERP_API_KEY = os.getenv("SERP_API_KEY")

SOCIAL_DOMAINS = [
    "linkedin.com",
    "instagram.com",
    "facebook.com",
    "tiktok.com"
]

async def fetch_data(query: str):
    results = []
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
                organic_results = data.get("organic_results", [])

                for item in organic_results[:10]:  # ambil lebih banyak biar filtering gak kosong
                    link = item.get("link", "")
                    if link:
                        results.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "link": link
                        })
    except Exception as e:
        print(f"Error fetch API: {e}")

    return results


def is_social_link(url: str) -> bool:
    url = url.lower()
    return any(domain in url for domain in SOCIAL_DOMAINS)


def calculate_confidence(candidate_data, target_profile):
    """
    Confidence score sederhana:
    - Nama target muncul di title/snippet = +0.6
    - Domain medsos valid = +0.4
    """
    score = 0.0
    title = candidate_data.get("title", "").lower()
    snippet = candidate_data.get("snippet", "").lower()
    link = candidate_data.get("link", "").lower()
    nama_target = target_profile["nama"].lower()

    if nama_target in title or nama_target in snippet:
        score += 0.6

    if is_social_link(link):
        score += 0.4

    return min(score, 1.0)


async def run_scraper_logic(target_id, target_nama, target_keywords=None):
    """
    Fokus: cari satu kandidat terbaik per media sosial (LinkedIn, IG, FB, TikTok).
    """

    queries = [
        f'"{target_nama}" site:linkedin.com',
        f'"{target_nama}" site:instagram.com',
        f'"{target_nama}" site:facebook.com',
        f'"{target_nama}" site:tiktok.com'
    ]

    all_raw_results = []
    seen_links = set()

    # 1. Fetch data dari semua query
    for query in queries:
        keyword_results = await fetch_data(query)
        for res in keyword_results:
            if res["link"] not in seen_links and is_social_link(res["link"]):
                seen_links.add(res["link"])
                all_raw_results.append(res)

    # 2. Hitung score untuk semua kandidat
    scored_results = []
    target_profile = {"nama": target_nama}
    for candidate in all_raw_results:
        score = calculate_confidence(candidate, target_profile)
        candidate["score"] = score
        scored_results.append(candidate)

    # 3. LOGIKA BARU: Grouping per Domain untuk ambil Top 1 per Sosmed
    # Kita gunakan dictionary untuk menyimpan skor tertinggi yang ditemukan per domain
    best_per_social = {} # Format: {"linkedin.com": {data}, "instagram.com": {data}}

    for item in scored_results:
        link = item["link"].lower()
        # Identifikasi domain mana yang cocok
        detected_domain = None
        for domain in SOCIAL_DOMAINS:
            if domain in link:
                detected_domain = domain
                break
        
        if detected_domain:
            # Jika domain belum ada di dict ATAU skor item ini lebih tinggi dari yang sudah disimpan
            if detected_domain not in best_per_social or item["score"] > best_per_social[detected_domain]["score"]:
                best_per_social[detected_domain] = item

    # 4. Ubah kembali ke list dan sort berdasarkan skor tertinggi
    top_results = list(best_per_social.values())
    top_results.sort(key=lambda x: x["score"], reverse=True)

    # 5. Tentukan Best Match & Status
    best_match = top_results[0] if top_results else {
        "title": "",
        "snippet": "Data tidak ditemukan",
        "link": "",
        "score": 0.0
    }
    highest_score = best_match["score"]

    status = "UNTRACKED"
    if highest_score >= 0.8:
        status = "IDENTIFIED"
    elif highest_score >= 0.4:
        status = "MANUAL_VERIFICATION_REQUIRED"

    return {
        "score": highest_score,
        "data": top_results, # Isinya sekarang maksimal 4 item (1 per platform)
        "best_match": best_match,
        "status": status
    }

# async def run_scraper_logic(target_id, target_nama, target_keywords=None):
#     """
#     Fokus: cari kandidat akun medsos alumni (LinkedIn, IG, FB, TikTok).
#     Output tetap sama: list top_results + best_match + score.
#     """

#     queries = [
#         f'"{target_nama}" site:linkedin.com',
#         f'"{target_nama}" site:instagram.com',
#         f'"{target_nama}" site:facebook.com',
#         f'"{target_nama}" site:tiktok.com'
#     ]

#     all_raw_results = []
#     seen_links = set()

#     for query in queries:
#         keyword_results = await fetch_data(query)

#         for res in keyword_results:
#             if res["link"] not in seen_links and is_social_link(res["link"]):
#                 seen_links.add(res["link"])
#                 all_raw_results.append(res)

#     scored_results = []
#     target_profile = {"nama": target_nama}

#     for candidate in all_raw_results:
#         score = calculate_confidence(candidate, target_profile)
#         scored_results.append({
#             "title": candidate.get("title", ""),
#             "snippet": candidate.get("snippet", ""),
#             "link": candidate.get("link", ""),
#             "score": score
#         })

#     scored_results.sort(key=lambda x: x["score"], reverse=True)

#     top_results = scored_results[:5]
#     highest_score = top_results[0]["score"] if top_results else 0.0
#     best_match = top_results[0] if top_results else {
#         "title": "",
#         "snippet": "Data tidak ditemukan",
#         "link": "",
#         "score": 0.0
#     }

#     status = "UNTRACKED"
#     if highest_score >= 0.8:
#         status = "IDENTIFIED"
#     elif highest_score >= 0.4:
#         status = "MANUAL_VERIFICATION_REQUIRED"

#     return {
#         "score": highest_score,
#         "data": top_results,
#         "best_match": best_match,
#         "status": status
#     }