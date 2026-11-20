SELECT SYS_CONTEXT('USERENV', 'SESSION_USER') AS session_user
     , SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') AS current_schema
     , SYS_CONTEXT('USERENV', 'DB_NAME') AS database_name
     , SYS_CONTEXT('USERENV', 'SERVICE_NAME') AS service_name
     , SYS_CONTEXT('USERENV', 'SERVER_HOST') AS server_host
     , SYS_CONTEXT('USERENV', 'INSTANCE_NAME') AS instance_name
  FROM DUAL
;
