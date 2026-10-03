-- Mirror alembic 0045_chunk_embedding_model.py

ALTER TABLE master_resume_chunks
  ADD COLUMN IF NOT EXISTS embedding_model text;

UPDATE master_resume_chunks
SET embedding_model = 'text-embedding-3-small'
WHERE embedding_model IS NULL;
