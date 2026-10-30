

USE movie_dw;

-- ---------------------------------------------------------------------
-- 1. Which movie has the highest average rating?
-- ---------------------------------------------------------------------
SELECT 
    m.title,
    m.release_year,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    COUNT(r.rating) AS total_reviews
FROM movies m
JOIN ratings r ON m.movie_id = r.movie_id
GROUP BY m.movie_id, m.title, m.release_year
HAVING COUNT(r.rating) >= 20
ORDER BY avg_rating DESC
LIMIT 1;


-- ---------------------------------------------------------------------
-- 2. What are the top 5 movie genres that have the highest average rating?
-- ---------------------------------------------------------------------
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


-- ---------------------------------------------------------------------
-- 3. Who is the director with the most movies in this dataset?
-- ---------------------------------------------------------------------
SELECT 
    director,
    COUNT(*) AS movie_count
FROM movies
WHERE director IS NOT NULL AND director != 'N/A'
GROUP BY director
ORDER BY movie_count DESC
LIMIT 1;


-- ---------------------------------------------------------------------
-- 4. What is the average rating of movies released each year?
-- ---------------------------------------------------------------------
SELECT 
    release_year,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    COUNT(r.rating) AS total_ratings
FROM movies m
JOIN ratings r ON m.movie_id = r.movie_id
WHERE release_year IS NOT NULL
GROUP BY release_year
ORDER BY release_year DESC;
