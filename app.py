"""
Movie Data Pipeline - Interactive Analytics Dashboard
Author: Bhumika Hiremath
Run with: streamlit run app.py
"""

import os
import re
import time
import pandas as pd
import requests
import mysql.connector
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

# Page Configuration
st.set_page_config(
    page_title="Movie Data Pipeline Analytics",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "movie_dw")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "").strip()


def get_db_connection():
    """Connects to MySQL database."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4"
    )


def run_query(sql_query, params=None):
    """Executes a SQL query and returns a Pandas DataFrame."""
    conn = get_db_connection()
    try:
        df = pd.read_sql(sql_query, conn, params=params)
        return df
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sidebar & Header
# ---------------------------------------------------------------------------
st.sidebar.title("🎬 Movie Pipeline Hub")
st.sidebar.markdown(f"**Connected Database:** `{DB_NAME}`")
st.sidebar.markdown(f"**Host:** `{DB_HOST}:{DB_PORT}`")
st.sidebar.markdown(f"**User:** `{DB_USER}`")
st.sidebar.divider()
st.sidebar.markdown(
    """
    ### 📌 About
    This interactive dashboard visualizes analytical insights from our normalized 
    **MovieLens** warehouse and **OMDb API** enrichments.
    
    - **Warehouse Schema:** 3NF / 1NF MySQL
    - **Pipeline Engine:** Pure Python & SQL
    - **Visualizations:** Plotly & Streamlit
    """
)

# Header
st.title("🍿 Movie Data Engineering Analytics Dashboard")
st.markdown("Visual data exploration built on top of our normalized **MySQL** warehouse & **OMDb API**.")

# Quick KPI Metrics
try:
    kpi_query = """
        SELECT 
            (SELECT COUNT(*) FROM movies) AS total_movies,
            (SELECT COUNT(*) FROM ratings) AS total_ratings,
            (SELECT COUNT(*) FROM genres) AS total_genres,
            (SELECT COUNT(*) FROM movies WHERE director IS NOT NULL) AS enriched_movies;
    """
    kpis = run_query(kpi_query).iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎬 Total Movies", f"{int(kpis['total_movies']):,}")
    col2.metric("⭐ Total Ratings", f"{int(kpis['total_ratings']):,}")
    col3.metric("🏷️ Distinct Genres", f"{int(kpis['total_genres']):,}")
    col4.metric("✨ Enriched via OMDb", f"{int(kpis['enriched_movies']):,}")
except Exception as e:
    st.error(f"Could not connect to database '{DB_NAME}'. Please ensure MySQL is running. Error: {e}")
    st.stop()

st.divider()

# Navigation Tabs
tab1, tab2, tab3 = st.tabs([
    "📊 Core Assignment Analytics",
    "⌨️ Custom SQL Query Playground & Auto-Charting",
    "🔍 Movie Explorer & Live OMDb Enrichment"
])

# ---------------------------------------------------------------------------
# TAB 1: Core Assignment Analytics
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Task 5 Analytical Visualizations")
    st.markdown("These visualizations correspond to the four core analytical questions solved in `queries.sql`.")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 1. Top Rated Movies")
        min_votes = st.slider("Minimum Reviews Threshold:", min_value=1, max_value=100, value=20, step=5)
        top_movies_sql = f"""
            SELECT 
                m.title,
                m.release_year,
                ROUND(AVG(r.rating), 2) AS avg_rating,
                COUNT(r.rating) AS total_reviews
            FROM movies m
            JOIN ratings r ON m.movie_id = r.movie_id
            GROUP BY m.movie_id, m.title, m.release_year
            HAVING COUNT(r.rating) >= {min_votes}
            ORDER BY avg_rating DESC
            LIMIT 10;
        """
        top_movies_df = run_query(top_movies_sql)
        st.dataframe(top_movies_df, use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("#### 2. Top 5 Movie Genres by Average Rating")
        genres_sql = """
            SELECT 
                g.genre_name,
                ROUND(AVG(r.rating), 2) AS avg_rating,
                COUNT(r.rating) AS total_ratings
            FROM genres g
            JOIN movie_genres mg ON g.genre_id = mg.genre_id
            JOIN ratings r ON mg.movie_id = r.movie_id
            WHERE g.genre_name != '(no genres listed)'
            GROUP BY g.genre_name
            ORDER BY avg_rating DESC
            LIMIT 5;
        """
        genres_df = run_query(genres_sql)
        fig_genres = px.bar(
            genres_df,
            x="genre_name",
            y="avg_rating",
            text="avg_rating",
            color="avg_rating",
            color_continuous_scale="Viridis",
            labels={"genre_name": "Genre", "avg_rating": "Average Rating (out of 5)"},
            title="Top 5 Highest-Rated Genres"
        )
        fig_genres.update_layout(yaxis=dict(range=[3.0, 4.2]))
        st.plotly_chart(fig_genres, use_container_width=True)

    st.divider()

    col_trend, col_director = st.columns([3, 2])

    with col_trend:
        st.markdown("#### 4. Yearly Rating Trends (1902 - 2018)")
        year_sql = """
            SELECT 
                release_year,
                ROUND(AVG(r.rating), 2) AS avg_rating,
                COUNT(r.rating) AS total_ratings
            FROM movies m
            JOIN ratings r ON m.movie_id = r.movie_id
            WHERE release_year IS NOT NULL
            GROUP BY release_year
            ORDER BY release_year ASC;
        """
        year_df = run_query(year_sql)
        fig_year = px.line(
            year_df,
            x="release_year",
            y="avg_rating",
            markers=True,
            title="Historical Average Movie Rating by Year",
            labels={"release_year": "Release Year", "avg_rating": "Average Rating"}
        )
        st.plotly_chart(fig_year, use_container_width=True)

    with col_director:
        st.markdown("#### 3. Top Directors by Movie Count")
        director_sql = """
            SELECT 
                director,
                COUNT(*) AS movie_count
            FROM movies
            WHERE director IS NOT NULL AND director != 'N/A'
            GROUP BY director
            ORDER BY movie_count DESC
            LIMIT 10;
        """
        director_df = run_query(director_sql)
        fig_dir = px.bar(
            director_df,
            x="movie_count",
            y="director",
            orientation="h",
            text="movie_count",
            color="movie_count",
            color_continuous_scale="Blues",
            title="Top 10 Directors (OMDb Enriched)"
        )
        fig_dir.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_dir, use_container_width=True)
        st.dataframe(director_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# TAB 2: Custom SQL Query Playground & Auto-Charting
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("⌨️ Interactive SQL Query Console & Live Charting Engine")
    st.markdown(
        "Execute **any arbitrary SQL query** against the database. The engine immediately displays the result table "
        "and automatically generates interactive Plotly visualizations!"
    )

    # Schema helper accordion
    with st.expander("ℹ️ Click to view Database Schema Reference (Tables & Columns)"):
        st.markdown("""
        - **`movies`**: `movie_id` (PK), `title`, `release_year`, `decade`, `imdb_id`, `director`, `plot`, `box_office`
        - **`genres`**: `genre_id` (PK), `genre_name`
        - **`movie_genres`**: `movie_id` (FK), `genre_id` (FK)
        - **`ratings`**: `rating_id` (PK), `user_id`, `movie_id` (FK), `rating`, `rated_at`
        """)

    # Preset templates
    preset_queries = {
        "Custom (Write your own)": "SELECT movie_id, title, release_year, decade, director, box_office FROM movies LIMIT 10;",
        "Average rating and total movies grouped by Decade": """SELECT 
    m.decade,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    COUNT(DISTINCT m.movie_id) AS total_movies,
    COUNT(r.rating) AS total_ratings
FROM movies m
JOIN ratings r ON m.movie_id = r.movie_id
WHERE m.decade IS NOT NULL
GROUP BY m.decade
ORDER BY m.decade ASC;""",
        "Top 10 highest box office movies enriched from OMDb": """SELECT 
    title,
    release_year,
    director,
    box_office
FROM movies
WHERE box_office IS NOT NULL
ORDER BY box_office DESC
LIMIT 10;""",
        "Count of movies in each genre": """SELECT 
    g.genre_name,
    COUNT(mg.movie_id) AS total_movies
FROM genres g
JOIN movie_genres mg ON g.genre_id = mg.genre_id
GROUP BY g.genre_id, g.genre_name
ORDER BY total_movies DESC;""",
        "Distribution of ratings (1.0 to 5.0 stars)": """SELECT 
    rating,
    COUNT(*) AS total_votes
FROM ratings
GROUP BY rating
ORDER BY rating ASC;""",
        "Top 10 most reviewed movies": """SELECT 
    m.title,
    m.release_year,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    COUNT(r.rating) AS review_count
FROM movies m
JOIN ratings r ON m.movie_id = r.movie_id
GROUP BY m.movie_id, m.title, m.release_year
ORDER BY review_count DESC
LIMIT 10;"""
    }

    selected_preset = st.selectbox(
        "Choose a sample query template or write custom SQL below:",
        list(preset_queries.keys())
    )

    # Initialize session state for SQL editor
    if "sql_editor_content" not in st.session_state or st.session_state.get("prev_preset") != selected_preset:
        st.session_state["sql_editor_content"] = preset_queries[selected_preset]
        st.session_state["prev_preset"] = selected_preset

    user_sql = st.text_area("SQL Statement:", value=st.session_state["sql_editor_content"], height=150)

    # Execution button
    execute_clicked = st.button("🚀 Execute Query", type="primary")

    if execute_clicked:
        start_time = time.time()
        try:
            df_res = run_query(user_sql)
            elapsed = time.time() - start_time
            st.session_state["last_query_df"] = df_res
            st.session_state["last_query_time"] = elapsed
            st.session_state["last_query_error"] = None
        except Exception as err:
            st.session_state["last_query_df"] = None
            st.session_state["last_query_error"] = str(err)

    # Display results from session state (preserves charts when tweaking dropdowns/radios)
    if st.session_state.get("last_query_error"):
        st.error(f"❌ SQL Execution Error: {st.session_state['last_query_error']}")

    elif st.session_state.get("last_query_df") is not None:
        custom_df = st.session_state["last_query_df"]
        elapsed = st.session_state.get("last_query_time", 0.0)

        st.success(f"✅ Query executed successfully: **{len(custom_df):,}** rows returned in **{elapsed:.3f}** seconds.")

        # Table & CSV Download
        st.dataframe(custom_df, use_container_width=True)
        csv_data = custom_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv_data,
            file_name="query_results.csv",
            mime="text/csv"
        )

        # Dynamic Auto-Charting Engine
        all_cols = list(custom_df.columns)
        num_cols = custom_df.select_dtypes(include=['number']).columns.tolist()
        cat_cols = [c for c in all_cols if c not in num_cols]

        if len(custom_df) > 0 and (len(num_cols) >= 1 or len(all_cols) >= 2):
            st.markdown("---")
            st.markdown("### 📈 Live Dynamic Visualization")

            c_controls1, c_controls2, c_controls3 = st.columns(3)

            with c_controls1:
                chart_type = st.selectbox(
                    "Chart Type:",
                    ["Bar Chart (Vertical)", "Bar Chart (Horizontal)", "Line Chart", "Area Chart", "Scatter Plot", "Pie / Donut Chart"]
                )

            with c_controls2:
                default_x = cat_cols[0] if cat_cols else all_cols[0]
                x_col = st.selectbox("X-Axis (Category / Dimension):", all_cols, index=all_cols.index(default_x))

            with c_controls3:
                default_y = num_cols[0] if num_cols else all_cols[-1]
                y_col = st.selectbox("Y-Axis (Metric / Value):", all_cols, index=all_cols.index(default_y))

            # Render selected chart
            try:
                # Limit plotted rows for high-density queries to keep browser responsive
                plot_df = custom_df.head(200) if len(custom_df) > 200 else custom_df
                if len(custom_df) > 200:
                    st.info(f"Showing first 200 rows in visualization for optimal rendering performance.")

                if chart_type == "Bar Chart (Vertical)":
                    fig = px.bar(
                        plot_df, x=x_col, y=y_col,
                        color=y_col if y_col in num_cols else None,
                        title=f"{y_col} by {x_col}",
                        template="plotly_white"
                    )
                elif chart_type == "Bar Chart (Horizontal)":
                    fig = px.bar(
                        plot_df, x=y_col, y=x_col, orientation="h",
                        color=y_col if y_col in num_cols else None,
                        title=f"{y_col} by {x_col}",
                        template="plotly_white"
                    )
                elif chart_type == "Line Chart":
                    fig = px.line(
                        plot_df, x=x_col, y=y_col, markers=True,
                        title=f"{y_col} across {x_col}",
                        template="plotly_white"
                    )
                elif chart_type == "Area Chart":
                    fig = px.area(
                        plot_df, x=x_col, y=y_col,
                        title=f"{y_col} Area across {x_col}",
                        template="plotly_white"
                    )
                elif chart_type == "Scatter Plot":
                    fig = px.scatter(
                        plot_df, x=x_col, y=y_col,
                        color=y_col if y_col in num_cols else None,
                        size=y_col if y_col in num_cols and (plot_df[y_col] > 0).all() else None,
                        title=f"Scatter: {y_col} vs {x_col}",
                        template="plotly_white"
                    )
                elif chart_type == "Pie / Donut Chart":
                    fig = px.pie(
                        plot_df.head(15), names=x_col, values=y_col,
                        hole=0.4,
                        title=f"{y_col} Share by {x_col} (Top 15)",
                        template="plotly_white"
                    )

                st.plotly_chart(fig, use_container_width=True)

            except Exception as chart_err:
                st.warning(f"Could not render the chosen chart for these columns: {chart_err}")


# ---------------------------------------------------------------------------
# TAB 3: Movie Explorer & Live OMDb Enrichment
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("🔍 Movie Explorer & On-Demand OMDb Enrichment")
    st.markdown(
        "Search any movie from the dataset. If it's missing OMDb details (director, plot, box office), "
        "click the enrichment button to call OMDb API live and persist it directly into MySQL!"
    )

    # Search box for movies
    movie_list = run_query("SELECT movie_id, title, release_year, imdb_id, director FROM movies ORDER BY title ASC;")
    movie_options = {f"{row['title']} ({row['release_year']})": row for _, row in movie_list.iterrows()}

    selected_name = st.selectbox("Select or search a movie:", list(movie_options.keys()))

    if selected_name:
        sel = movie_options[selected_name]
        mid = int(sel["movie_id"])

        # Fetch detailed movie info from MySQL
        movie_detail_sql = """
            SELECT 
                m.movie_id,
                m.title,
                m.release_year,
                m.decade,
                m.imdb_id,
                m.director,
                m.plot,
                m.box_office,
                ROUND(AVG(r.rating), 2) AS avg_rating,
                COUNT(r.rating) AS total_reviews
            FROM movies m
            LEFT JOIN ratings r ON m.movie_id = r.movie_id
            WHERE m.movie_id = %s
            GROUP BY m.movie_id;
        """
        detail_df = run_query(movie_detail_sql, params=(mid,)).iloc[0]

        # Fetch genres for this movie
        genres_sql = """
            SELECT g.genre_name 
            FROM genres g
            JOIN movie_genres mg ON g.genre_id = mg.genre_id
            WHERE mg.movie_id = %s;
        """
        movie_genres_df = run_query(genres_sql, params=(mid,))
        genre_tags = movie_genres_df["genre_name"].tolist() if not movie_genres_df.empty else ["Unknown"]

        st.markdown(f"### {detail_df['title']} ({detail_df['release_year']})")
        st.markdown(f"**🏷️ Genres:** " + " ".join([f"`{g}`" for g in genre_tags]))

        m_col1, m_col2 = st.columns([2, 1])

        with m_col1:
            st.markdown(f"**🎬 Director:** {detail_df['director'] if pd.notna(detail_df['director']) else '*Not yet enriched*'}")
            st.markdown(f"**📖 Plot:** {detail_df['plot'] if pd.notna(detail_df['plot']) else '*No plot available*'}")
            
            box_text = f"${detail_df['box_office']:,.2f}" if pd.notna(detail_df['box_office']) else "N/A"
            st.markdown(f"**💰 Box Office:** `{box_text}`")
            st.markdown(f"**📅 Decade:** `{detail_df['decade']}`")
            st.markdown(f"**🔗 IMDb ID:** `{detail_df['imdb_id']}`")

        with m_col2:
            st.metric("⭐ Avg Rating", f"{detail_df['avg_rating']} / 5.0" if pd.notna(detail_df['avg_rating']) else "No ratings")
            st.metric("👥 Total Reviews", f"{int(detail_df['total_reviews']):,}" if pd.notna(detail_df['total_reviews']) else "0")

            # Live Enrichment Button if not yet enriched
            if pd.isna(detail_df['director']):
                st.warning("⚠️ This movie is missing OMDb details!")
                if st.button("✨ Enrich with OMDb API Now!", type="primary"):
                    if not OMDB_API_KEY:
                        st.error("Please add your OMDB_API_KEY in .env to use live enrichment.")
                    else:
                        with st.spinner("Calling OMDb API..."):
                            imdb_key = str(detail_df['imdb_id']) if pd.notna(detail_df['imdb_id']) else None
                            params = {"apikey": OMDB_API_KEY}
                            if imdb_key:
                                params["i"] = imdb_key
                            else:
                                params["t"] = detail_df['title']

                            resp = requests.get("http://www.omdbapi.com/", params=params, timeout=5)
                            if resp.status_code == 200 and resp.json().get("Response") == "True":
                                api_res = resp.json()
                                d_val = api_res.get("Director") if api_res.get("Director") != "N/A" else None
                                p_val = api_res.get("Plot") if api_res.get("Plot") != "N/A" else None
                                b_val = api_res.get("BoxOffice")
                                b_num = None
                                if b_val and b_val != "N/A":
                                    try:
                                        b_num = float(re.sub(r'[\$,\s]', '', str(b_val)))
                                    except:
                                        pass

                                # Update MySQL directly
                                update_conn = get_db_connection()
                                u_cur = update_conn.cursor()
                                u_cur.execute("""
                                    UPDATE movies 
                                    SET director = %s, plot = %s, box_office = %s
                                    WHERE movie_id = %s;
                                """, (d_val, p_val, b_num, mid))
                                update_conn.commit()
                                u_cur.close()
                                update_conn.close()

                                st.success("🎉 Enriched successfully! Reloading...")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Movie not found in OMDb API or rate limit reached.")
