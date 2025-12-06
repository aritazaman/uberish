DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS ratings;


CREATE TABLE user (
    username TEXT UNIQUE NOT NULL,
    email TEXT PRIMARY KEY,
    firstName TEXT,
    lastName TEXT,
    hashPass TEXT NOT NULL,
    salt TEXT NOT NULL,
    isDriver TEXT
);

CREATE TABLE ratings(
    reviewer TEXT NOT NULL, 
    reviewee TEXT NOT NULL, 
    rating INTEGER NOT NULL, 
    FOREIGN KEY (reviewer) REFERENCES user(username), 
    FOREIGN KEY (reviewer) REFERENCES user(username)
);

