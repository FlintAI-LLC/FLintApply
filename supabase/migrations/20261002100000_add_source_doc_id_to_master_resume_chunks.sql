ALTER TABLE master_resume_chunks
  ADD COLUMN IF NOT EXISTS source_doc_id UUID REFERENCES master_resumes(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_master_resume_chunks_source_doc_id
  ON master_resume_chunks (source_doc_id);
