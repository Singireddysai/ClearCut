const API_BASE = "/api";

export type JobStatus =
  | "pending"
  | "uploading"
  | "ingesting"
  | "analyzing"
  | "segmenting"
  | "summarizing"
  | "assembling"
  | "evaluating"
  | "completed"
  | "failed";

export interface Job {
  id: string;
  filename: string;
  status: JobStatus;
  current_step: string;
  current_length: string | null;
  error: string | null;
  video_path: string | null;
  run_id: string | null;
  progress_pct: number;
}

export interface UploadResponse {
  job_id: string;
  filename: string;
  status: string;
}

export interface OutputItem {
  length: string;
  video: string;
  filename: string;
}

export interface TranscriptItem {
  length: string;
  transcript: string;
  filename: string;
}

export interface OutputsResponse {
  job_id: string;
  outputs: OutputItem[];
  transcripts: TranscriptItem[];
}

export async function uploadVideo(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function listJobs(): Promise<{ jobs: Job[] }> {
  const res = await fetch(`${API_BASE}/jobs`);
  if (!res.ok) throw new Error("Failed to list jobs");
  return res.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error("Job not found");
    throw new Error("Failed to get job");
  }
  return res.json();
}

export async function getOutputs(jobId: string): Promise<OutputsResponse> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/outputs`);
  if (!res.ok) throw new Error("Failed to get outputs");
  return res.json();
}

export function downloadUrl(jobId: string, length: string): string {
  return `${API_BASE}/jobs/${jobId}/download/${length}`;
}

export function transcriptUrl(jobId: string, length: string): string {
  return `${API_BASE}/jobs/${jobId}/transcript/${length}`;
}
