-- For MySQL:

USE crud;  -- pre-existing database

CREATE TABLE ut (a INTEGER PRIMARY KEY, b INTEGER);

INSERT INTO ut (a, b) VALUES (1, 101);  -- OK
INSERT INTO ut (a, b) VALUES (2, 102);  -- OK

INSERT INTO ut (a, b) VALUES (1, 101);  -- fails; duplicate key

INSERT INTO ut (a, b) VALUES (1, 101) ON DUPLICATE KEY UPDATE a = 1, b = 103;
    -- succeeds and changes only one row

SELECT * FROM ut;
