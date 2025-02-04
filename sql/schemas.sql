-- The schema used to create the table. If you change anything here, please change the table name, and column name
--      lookup in main.py. We will add more schemas eventually, break them up with:
-- ###BREAK
-- Schema[1]
CREATE TABLE IF NOT EXISTS Codex (
    guid TEXT PRIMARY KEY,
    section TEXT,
    data JSONB
);
-- ###BREAK
-- Schema[2] etc