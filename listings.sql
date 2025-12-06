DROP TABLE IF EXISTS listing;

CREATE TABLE listing (
    username TEXT NOT NULL,
    day TEXT, 
    cents INTEGER, 
    listingID INTEGER PRIMARY KEY
);
