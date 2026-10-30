
-- =====================================================================
-- Movie Data Pipeline - Database Schema (MySQL)
-- Designed for MovieLens + OMDb enriched movie analytics
-- =====================================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- Table 1: movies
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movies (
    movie_id INT NOT NULL,                          
    title VARCHAR(255) NOT NULL,                    
    release_year INT NULL,                          
    decade VARCHAR(10) NULL,                        
    imdb_id VARCHAR(20) NULL,                       
    director VARCHAR(255) NULL,                     
    plot TEXT NULL,                                 
    box_office DECIMAL(15, 2) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (movie_id),
    INDEX idx_movies_year (release_year),
    INDEX idx_movies_director (director(100)),
    INDEX idx_movies_imdb_id (imdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 2: genres
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS genres (
    genre_id INT AUTO_INCREMENT NOT NULL,
    genre_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (genre_id),
    UNIQUE KEY uq_genre_name (genre_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 3: movie_genres
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id INT NOT NULL,
    genre_id INT NOT NULL,
    PRIMARY KEY (movie_id, genre_id),
    INDEX idx_mg_genre_id (genre_id),
    CONSTRAINT fk_mg_movies FOREIGN KEY (movie_id) REFERENCES movies (movie_id) ON DELETE CASCADE,
    CONSTRAINT fk_mg_genres FOREIGN KEY (genre_id) REFERENCES genres (genre_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 4: ratings
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ratings (
    rating_id BIGINT AUTO_INCREMENT NOT NULL,
    user_id INT NOT NULL,
    movie_id INT NOT NULL,
    rating DECIMAL(3, 1) NOT NULL,                  
    rating_timestamp DATETIME NULL,                 
    PRIMARY KEY (rating_id),
    UNIQUE KEY uq_user_movie (user_id, movie_id),   
    INDEX idx_ratings_movie_id (movie_id),
    INDEX idx_ratings_user_id (user_id),
    INDEX idx_ratings_rating (rating),
    CONSTRAINT fk_ratings_movies FOREIGN KEY (movie_id) REFERENCES movies (movie_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

