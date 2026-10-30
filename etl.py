#!/usr/bin/env python3
"""
Movie Data Pipeline
"""

import os
import re
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
import mysql.connector
from dotenv import load_dotenv

# Load database and API credentials from .env file
load_dotenv()

# Define project file paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "raw"
CACHE_PATH = BASE_DIR / "data" / "cache" / "omdb_cache.json"
SCHEMA_PATH = BASE_DIR / "schema.sql"

# Database connection configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "movie_dw")
}

# OMDb API settings
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "").strip()
FETCH_LIMIT = int(os.getenv("OMDB_FETCH_LIMIT", "100"))  # Limit new API calls per run


# ---------------------------------------------------------------------------
# Database Setup
# ---------------------------------------------------------------------------
def get_db(with_database=True):
    """Creates and returns a connection to the MySQL database."""
    cfg = DB_CONFIG.copy()
    if not with_database:
        cfg.pop("database", None)
    return mysql.connector.connect(**cfg)


def init_database_schema():
    """Reads schema.sql and creates tables/indexes in MySQL if they do not exist."""
    # Step 1: Create the database if it doesn't exist
    conn = get_db(with_database=False)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` CHARACTER SET utf8mb4;")
    conn.commit()
    cursor.close()
    conn.close()

    # Step 2: Execute schema.sql table definitions
    conn = get_db()
    cursor = conn.cursor()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        # Filter out SQL comments
        clean_sql = "\n".join(l for l in f.read().splitlines() if not l.strip().startswith("--"))

    # Execute each SQL statement separated by semicolon
    for stmt in clean_sql.split(";"):
        if stmt.strip():
            cursor.execute(stmt.strip())

    conn.commit()
    cursor.close()
    conn.close()


# ---------------------------------------------------------------------------
# 1. EXTRACT & ENRICH
# ---------------------------------------------------------------------------
def fetch_omdb_movie(imdb_id, title, year, cache):
    """
    Fetches movie details (Director, Plot, BoxOffice) from OMDb API.
    Checks the local disk cache first to save daily API quota.
    """
    # Use IMDb ID as cache key, or fallback to 'title_year'
    key = imdb_id if imdb_id else f"{title}_{year}".lower()
    if key in cache:
        return cache[key], False  # Return cached data (no network call)

    # Skip API request if no key is provided or still the default placeholder
    if not OMDB_API_KEY or OMDB_API_KEY == "your_omdb_api_key_here":
        return None, "HALT"

    params = {"apikey": OMDB_API_KEY}
    if imdb_id:
        params["i"] = imdb_id  
    elif title:
        params["t"] = title
        if year:
            params["y"] = str(year)
    else:
        return None, False

    try:
        resp = requests.get("http://www.omdbapi.com/", params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("Response") == "True":
                cache[key] = data  # Save to cache
                return data, True  # Network call was successful
            elif data.get("Error") in ["Invalid API key!", "Request limit reached!"]:
                print(f"⚠️ OMDb API: {data.get('Error')} Halting further API calls.")
                return None, "HALT"
            else:
                cache[key] = {"Response": "False"}
                return None, True
        elif resp.status_code in [401, 429]:
            print("⚠️ OMDb API returned status 401/429 (Invalid key or quota exceeded). Halting further API calls.")
            return None, "HALT"
    except Exception:
        pass

    return None, True


def extract_data():
    """Reads movies.csv, ratings.csv, and links.csv into Pandas DataFrames."""
    movies_df = pd.read_csv(DATA_DIR / "movies.csv")
    ratings_df = pd.read_csv(DATA_DIR / "ratings.csv")
    links_df = pd.read_csv(DATA_DIR / "links.csv") if (DATA_DIR / "links.csv").exists() else None
    return movies_df, ratings_df, links_df


# ---------------------------------------------------------------------------
# 2. TRANSFORM
# ---------------------------------------------------------------------------
def clean_movie_title(raw_title):
    """
    Extracts 4-digit release year, derives decade (e.g. 1990s),
    and normalizes trailing articles (e.g. 'Matrix, The' -> 'The Matrix').
    """
    if not isinstance(raw_title, str) or not raw_title.strip():
        return "Unknown", None, None

    title = raw_title.strip()

    # Extract year in parenthesis at the end of the title, e.g. (1995)
    match = re.search(r'\s*\((\d{4})\)\s*$', title)
    year = int(match.group(1)) if match else None
    if match:
        title = title[:match.start()].strip()

    # Move trailing articles to the front (e.g., 'Godfather, The' -> 'The Godfather')
    for art in ["The", "A", "An", "Le", "La", "Les", "Der", "Die", "Das", "El", "Il"]:
        if title.endswith(f", {art}"):
            title = f"{art} " + title[:-len(f", {art}")]
            break

    # calculate decade (e.g., 1995 -> '1990s')
    decade = f"{(year // 10) * 10}s" if year else None
    return title, year, decade


def parse_box_office(val):
    """Cleans currency string (e.g. '$373,554,033') into a numeric float."""
    if not val or val == "N/A":
        return None
    try:
        # Remove '$', commas, and whitespace
        return float(re.sub(r'[\$,\s]', '', str(val)))
    except (ValueError, TypeError):
        return None


def transform_and_enrich_movies(movies_df, links_df, cache):
    """
    Cleans movie titles, queries OMDb for additional details,
    and normalizes pipe-separated genres ('Action|Comedy') into 1NF.
    """
    # Merge with links.csv to obtain exact IMDb IDs (e.g. 'tt0114709')
    if links_df is not None:
        merged = movies_df.merge(links_df[["movieId", "imdbId"]], on="movieId", how="left")
    else:
        merged = movies_df.copy()
        merged["imdbId"] = None

    transformed_movies = []
    distinct_genres = set()
    movie_genres = []
    api_calls = 0

    for _, row in merged.iterrows():
        mid = int(row["movieId"])
        title, year, decade = clean_movie_title(str(row["title"]))

        # Format IMDb ID as 'tt' followed by 7 digits
        raw_imdb = str(row.get("imdbId", "")).strip().split(".")[0]
        imdb_id = f"tt{raw_imdb.zfill(7)}" if raw_imdb and raw_imdb != "nan" else None

        # Check local cache first, or make a limited number of live API calls
        director, plot, box_office = None, None, None
        key = imdb_id if imdb_id else f"{title}_{year}".lower()
        if key in cache or (FETCH_LIMIT <= 0 or api_calls < FETCH_LIMIT):
            omdb_data, api_status = fetch_omdb_movie(imdb_id, title, year, cache)
            if api_status == "HALT":
                api_calls = FETCH_LIMIT + 1  # Stop further network requests immediately
            elif api_status is True:
                api_calls += 1
                time.sleep(0.05)
            if omdb_data and omdb_data.get("Response") == "True":
                director = omdb_data.get("Director") if omdb_data.get("Director") != "N/A" else None
                plot = omdb_data.get("Plot") if omdb_data.get("Plot") != "N/A" else None
                box_office = parse_box_office(omdb_data.get("BoxOffice"))

        transformed_movies.append((mid, title, year, decade, imdb_id, director, plot, box_office))

        # Split pipe-separated genres into individual rows (First Normal Form)
        if pd.notna(row.get("genres")):
            for g in str(row["genres"]).split("|"):
                if g.strip():
                    distinct_genres.add(g.strip())
                    movie_genres.append((mid, g.strip()))

    # Save any newly fetched movie details to local disk cache
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    return transformed_movies, sorted(list(distinct_genres)), movie_genres, api_calls


def transform_ratings(ratings_df):
    """
    Cleans ratings data: removes nulls, validates range (0.5 to 5.0),
    and converts Unix epoch timestamp to standard SQL DATETIME.
    """
    # Drop records with missing values
    clean_df = ratings_df.dropna(subset=["userId", "movieId", "rating"])
    # Validate rating score boundary
    clean_df = clean_df[(clean_df["rating"] >= 0.5) & (clean_df["rating"] <= 5.0)]

    rating_rows = []
    for _, r in clean_df.iterrows():
        raw_ts = r.get("timestamp")
        # Convert Unix epoch integer (e.g. 964982703) to 'YYYY-MM-DD HH:MM:SS'
        dt_str = (
            datetime.fromtimestamp(int(raw_ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if pd.notna(raw_ts)
            else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )
        rating_rows.append((int(r["userId"]), int(r["movieId"]), float(r["rating"]), dt_str))
    return rating_rows


# ---------------------------------------------------------------------------
# 3. LOAD (Idempotent SQL Inserts)
# ---------------------------------------------------------------------------
def load_data_to_mysql(movies, genres, movie_genres, ratings, batch_size=5000):
    """
    Loads all transformed records into MySQL.
    Uses ON DUPLICATE KEY UPDATE so running multiple times will not duplicate rows.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Insert unique genres into 'genres' table
        cursor.executemany(
            "INSERT INTO genres (genre_name) VALUES (%s) ON DUPLICATE KEY UPDATE genre_name=VALUES(genre_name);",
            [(g,) for g in genres]
        )
        conn.commit()

        # Build genre_name -> genre_id map for the bridge table
        cursor.execute("SELECT genre_name, genre_id FROM genres;")
        genre_map = {row[0]: row[1] for row in cursor.fetchall()}

        # 2. Insert movie records into 'movies' table in batches
        movie_sql = """
            INSERT INTO movies (movie_id, title, release_year, decade, imdb_id, director, plot, box_office)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title=VALUES(title), release_year=VALUES(release_year), decade=VALUES(decade),
                imdb_id=VALUES(imdb_id), director=COALESCE(VALUES(director), director),
                plot=COALESCE(VALUES(plot), plot), box_office=COALESCE(VALUES(box_office), box_office);
        """
        for i in range(0, len(movies), batch_size):
            cursor.executemany(movie_sql, movies[i : i + batch_size])
        conn.commit()

        # 3. Insert relationships into 'movie_genres' bridge table
        mg_rows = [(mid, genre_map[g]) for mid, g in movie_genres if g in genre_map]
        for i in range(0, len(mg_rows), batch_size):
            cursor.executemany(
                "INSERT IGNORE INTO movie_genres (movie_id, genre_id) VALUES (%s, %s);",
                mg_rows[i : i + batch_size]
            )
        conn.commit()

        # 4. Insert user ratings into 'ratings' table in batches of 5,000
        rating_sql = """
            INSERT INTO ratings (user_id, movie_id, rating, rating_timestamp)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE rating=VALUES(rating);
        """
        for i in range(0, len(ratings), batch_size):
            cursor.executemany(rating_sql, ratings[i : i + batch_size])
        conn.commit()

    except Exception as e:
        conn.rollback()  # Roll back on error to keep database consistent
        raise e
    finally:
        cursor.close()
        conn.close()


def print_summary():
    """Queries and displays final row counts for all database tables."""
    conn = get_db()
    cursor = conn.cursor()
    print("\n" + "=" * 50)
    print("           DATABASE LOAD SUMMARY")
    print("=" * 50)
    for tbl in ["movies", "genres", "movie_genres", "ratings"]:
        cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
        print(f"  • {tbl:14}: {cursor.fetchone()[0]:>8,} rows")
    cursor.execute("SELECT COUNT(*) FROM movies WHERE director IS NOT NULL;")
    print(f"  • Enriched Movies: {cursor.fetchone()[0]:>8,} rows")
    print("=" * 50)
    cursor.close()
    conn.close()


# ---------------------------------------------------------------------------
# Main Pipeline Entry Point
# ---------------------------------------------------------------------------
def main():
    start = time.time()
    print("Starting Movie Data Pipeline ETL...")

    # Step 1: Initialize database schema
    print("1/4 Initializing database schema...")
    init_database_schema()

    # Step 2: Extract CSV data
    print("2/4 Extracting MovieLens CSV files...")
    movies_df, ratings_df, links_df = extract_data()

    # Step 3: Transform & enrich
    print("3/4 Transforming data & enriching with OMDb API...")
    cache = {}
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass

    movies, genres, movie_genres, api_calls = transform_and_enrich_movies(movies_df, links_df, cache)
    ratings = transform_ratings(ratings_df)

    # Step 4: Batch load into MySQL
    print("4/4 Loading data into MySQL...")
    load_data_to_mysql(movies, genres, movie_genres, ratings)

    # Display final row counts
    print_summary()
    print(f"Pipeline completed in {time.time() - start:.2f} seconds!")
    print("\nTo view analytical results, run: mysql -t movie_dw < queries.sql")


if __name__ == "__main__":
    main()
