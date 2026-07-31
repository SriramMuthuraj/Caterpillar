import axios from 'axios';

const envBaseUrl = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_BASE_URL;

// One backend, one port. The FastAPI app on :8000 serves the forecast and
// anomaly routes itself and mounts the Flask CRUD app underneath, so every
// endpoint in the product shares this origin and there is no second client.
// (Running the Flask app standalone on :5000 still works — set VITE_API_BASE_URL.)
const BASE_URL = envBaseUrl || 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // The forecast and anomaly endpoints read from a pre-warmed bundle, but the
  // very first request after a cold start can wait on it.
  timeout: 60000,
});

export const delay = (ms: number = 200) => new Promise((resolve) => setTimeout(resolve, ms));
