import axios from "axios";
import { useAuthStore } from "../store/auth";

const baseURL = "http://192.168.0.95/api/v1";

export const api = axios.create({
  baseURL,
  timeout: 30000,
});

api.interceptors.request.use((cfg) => {
  const token = useAuthStore.getState().token;

  if (token) {
    cfg.headers.Authorization = `Bearer ${token}`;
  }

  return cfg;
});