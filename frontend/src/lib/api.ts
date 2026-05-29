import axios from "axios";

export type UserRole = "manager" | "buyer";

export interface User {
  id: number;
  name: string;
  phone: string;
  role: UserRole;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type ProductCategory =
  | "phone"
  | "tablet"
  | "case"
  | "screen_protector"
  | "other";

export interface Product {
  id: number;
  name: string;
  category: ProductCategory;
  sku?: string;
  default_unit_cost?: number | null;
  created_at: string;
}

export type RequestStatus = "pending" | "done";

export interface RequestOut {
  id: number;
  product_id: number | null;
  product: Product | null;
  custom_product_name: string | null;
  quantity: number;
  status: RequestStatus;
  created_by_id: number;
  created_at: string;
  updated_at: string | null;
}

const TOKEN_KEY = "watchlist_token";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("auth:logout"));
    }
    return Promise.reject(error);
  }
);

export async function loginApi(
  phone: string,
  password: string
): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/login", {
    phone,
    password,
  });
  return data;
}

export async function searchProducts(query: string): Promise<Product[]> {
  const trimmed = query.trim();
  if (!trimmed) return [];
  const { data } = await api.get<Product[]>("/products", {
    params: { search: trimmed },
  });
  return data;
}

export async function createRequest(payload: {
  product_id?: number;
  custom_product_name?: string;
  quantity: number;
}): Promise<RequestOut> {
  const { data } = await api.post<RequestOut>("/requests", payload);
  return data;
}

export async function listRequests(params?: {
  status?: RequestStatus;
}): Promise<RequestOut[]> {
  const { data } = await api.get<RequestOut[]>("/requests", { params });
  return data;
}

export async function deleteRequest(id: number): Promise<void> {
  await api.delete(`/requests/${id}`);
}

export async function markDone(
  requestIds: number[]
): Promise<{ marked_count: number; request_ids: number[] }> {
  const { data } = await api.post<{
    marked_count: number;
    request_ids: number[];
  }>("/requests/mark-done", { request_ids: requestIds });
  return data;
}

export default api;
