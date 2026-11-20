SELECT USER AS username
     , SYS_CONTEXT('USERENV', 'DB_NAME') AS database_name
     , privilege
  FROM session_privs
 WHERE privilege IN ('CREATE TABLE', 'CREATE PROCEDURE', 'CREATE MINING MODEL')
 ORDER BY privilege
