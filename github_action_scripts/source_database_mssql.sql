USE sourcedb;

DROP TABLE IF EXISTS note;
GO

CREATE TABLE note (
  note_id int NOT NULL PRIMARY KEY,
  patient_id int NULL ,
  note text,
  note_datetime datetime NULL,
);
GO

DROP TABLE IF EXISTS patient;
GO

CREATE TABLE patient (
  patient_id int NOT NULL PRIMARY KEY,
  forename varchar(50) NULL,
  surname varchar(50) NULL,
  dob date NULL,
  nullfield int NULL,
  nhsnum bigint NULL,
  phone varchar(50) NULL,
  postcode varchar(50) NULL,
  optout tinyint NULL,
  related_patient_id int NULL,
);
GO
