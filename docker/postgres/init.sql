-- Runs once, on the first start of an empty volume. The dev database
-- (olmenta) is created by POSTGRES_DB.
CREATE DATABASE olmenta_test OWNER olmenta;
CREATE DATABASE olmenta_e2e OWNER olmenta;
