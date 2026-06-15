import axios from "axios";

export interface User {
  id: number;
  name: string;
  phone: string;
  plan: string;
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

export async function requestCode(phone: string): Promise<void> {
  await api.post("/auth/request-code", { phone });
}

export async function registerApi(payload: {
  name: string;
  phone: string;
  password: string;
  carrier?: string;
  code: string;
}): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/register", payload);
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

// ---- Contacts ----

export interface Contact {
  id: number;
  nickname: string;
  phone: string;
  linked_user_id: number | null;
  created_at: string;
}

export async function listContacts(): Promise<Contact[]> {
  const { data } = await api.get<Contact[]>("/contacts");
  return data;
}

export async function createContact(payload: {
  nickname: string;
  phone: string;
}): Promise<Contact> {
  const { data } = await api.post<Contact>("/contacts", payload);
  return data;
}

export async function updateContact(
  id: number,
  payload: { nickname?: string; phone?: string }
): Promise<Contact> {
  const { data } = await api.patch<Contact>(`/contacts/${id}`, payload);
  return data;
}

export async function deleteContact(id: number): Promise<void> {
  await api.delete(`/contacts/${id}`);
}

// ---- Lists ----

export interface ListItem {
  id: number;
  product_id: number | null;
  product: Product | null;
  custom_product_name: string | null;
  quantity: number;
}

export interface WatchList {
  id: number;
  title: string | null;
  items: ListItem[];
  created_at: string;
}

export async function createList(payload: {
  title?: string;
  items: Array<{
    product_id?: number;
    custom_product_name?: string;
    quantity: number;
  }>;
}): Promise<WatchList> {
  const { data } = await api.post<WatchList>("/lists", payload);
  return data;
}

export async function listLists(): Promise<WatchList[]> {
  const { data } = await api.get<WatchList[]>("/lists");
  return data;
}

export async function getList(id: number): Promise<WatchList> {
  const { data } = await api.get<WatchList>(`/lists/${id}`);
  return data;
}

export async function updateList(
  id: number,
  payload: { title?: string }
): Promise<WatchList> {
  const { data } = await api.patch<WatchList>(`/lists/${id}`, payload);
  return data;
}

export async function deleteList(id: number): Promise<void> {
  await api.delete(`/lists/${id}`);
}

// ---- Send ----

export interface SendOut {
  id: number;
  list_id: number;
  recipient_user_id: number | null;
  wa_link: string | null;
  created_at: string;
}

export type SendRecipient = { contact_id: number } | { phone: string };

export async function sendList(
  listId: number,
  recipients: SendRecipient[]
): Promise<SendOut[]> {
  const { data } = await api.post<SendOut[]>(`/lists/${listId}/send`, {
    recipients,
  });
  return data;
}

// ---- Inbox ----

export interface SendItemState {
  list_item_id: number;
  checked: boolean;
  received_quantity: number;
}

export interface InboxListItem {
  id: number;
  product_id: number | null;
  product_name: string | null;
  custom_product_name: string | null;
  quantity: number;
}

export interface InboxSend {
  id: number;
  list_id: number;
  list_title: string | null;
  sender_name?: string | null;
  items: InboxListItem[];
  item_states: SendItemState[];
  created_at: string;
}

export async function getInbox(): Promise<InboxSend[]> {
  const { data } = await api.get<InboxSend[]>("/inbox");
  return data;
}

export async function updateSendItem(
  sendId: number,
  listItemId: number,
  payload: { checked?: boolean; received_quantity?: number }
): Promise<SendItemState> {
  const { data } = await api.patch<SendItemState>(
    `/sends/${sendId}/items/${listItemId}`,
    payload
  );
  return data;
}

export async function markAllReceived(sendId: number): Promise<InboxSend> {
  const { data } = await api.post<InboxSend>(`/sends/${sendId}/mark-all-received`);
  return data;
}

export async function dismissSend(sendId: number): Promise<void> {
  await api.post(`/sends/${sendId}/dismiss`);
}

export async function clearInbox(): Promise<void> {
  await api.post("/inbox/clear");
}

export default api;
