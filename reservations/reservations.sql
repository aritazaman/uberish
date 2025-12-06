-- DROP TABLE IF EXISTS rides;

-- CREATE TABLE rides(
--     listingID INTEGER PRIMARY KEY, 
--     day TEXT, 
--     passenger TEXT, 
--     driver TEXT, 
--     price INTEGER
-- );

DROP TABLE IF EXISTS rides;

CREATE TABLE rides(
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    listingID INTEGER UNIQUE,
    passenger TEXT,
    driver TEXT,
    price INTEGER
);
