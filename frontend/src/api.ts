import axios from "axios";

export interface PodcastCreatePayload {
  title: string;
  description?: string | null;
  voice?: string | null;
  script?: string | null;
  source_urls?: string[];
  materials_set?: "1" | "2";
}

export type PodcastStatus =
  | "queued"
  | "running"
  | "done"
  | "failed"
  | "cancelled";

export interface PodcastItem {
  id: string;
  status: PodcastStatus;
  progress: number;
  title: string;
  description?: string | null;
  voice?: string | null;
  audio_url?: string | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PodcastListResponse {
  items: PodcastItem[];
  total: number;
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://localhost:3000",
  timeout: 30000,
});

export async function createPodcast(
  payload: PodcastCreatePayload
): Promise<{ id: string }> {
  const { data } = await api.post("/v1/podcasts", payload);
  return data;
}

export async function getPodcast(id: string): Promise<PodcastItem> {
  const { data } = await api.get(`/v1/podcasts/${id}`);
  return data;
}

export async function listPodcasts(
  params: Partial<{ status: PodcastStatus; limit: number; offset: number }> = {}
): Promise<PodcastListResponse> {
  const { data } = await api.get("/v1/podcasts", { params });
  return data;
}

export async function deletePodcast(id: string): Promise<PodcastItem> {
  const { data } = await api.delete(`/v1/podcasts/{id}`.replace("{id}", id));
  return data;
}
