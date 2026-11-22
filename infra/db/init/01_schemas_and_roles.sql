-- Runs once, on first container start.
-- Passwords below are for LOCAL DEVELOPMENT ONLY.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS analytics;  -- warehouse data (sensitive boundary)
CREATE SCHEMA IF NOT EXISTS knowledge;  -- RAG index (document boundary)

-- Role used by warehouse-mcp. Read-only is enforced by Postgres, not by prompts:
--   1. only SELECT is granted
--   2. every transaction is read-only by default
--   3. runaway queries are killed after 10s
CREATE ROLE agent_readonly LOGIN PASSWORD 'agent_readonly_dev';
ALTER ROLE agent_readonly SET default_transaction_read_only = on;
ALTER ROLE agent_readonly SET statement_timeout = '10s';
ALTER ROLE agent_readonly SET idle_in_transaction_session_timeout = '30s';
GRANT CONNECT ON DATABASE analytics TO agent_readonly;
GRANT USAGE ON SCHEMA analytics TO agent_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA analytics
    GRANT SELECT ON TABLES TO agent_readonly;

-- Role used by knowledge-mcp. Can read the RAG index, cannot see warehouse data.
CREATE ROLE knowledge_reader LOGIN PASSWORD 'knowledge_reader_dev';
ALTER ROLE knowledge_reader SET default_transaction_read_only = on;
ALTER ROLE knowledge_reader SET statement_timeout = '5s';
GRANT CONNECT ON DATABASE analytics TO knowledge_reader;
GRANT USAGE ON SCHEMA knowledge TO knowledge_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA knowledge
    GRANT SELECT ON TABLES TO knowledge_reader;

-- Neither role may create objects anywhere.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
