import axios from "axios";

export const apiClient = axios.create({
  baseURL: "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

// 🌟 NEW: Define the shape of our data
export interface FactoryLine {
  id: string;
  supervisor: string;
  // 🌟 NEW: Added "Blocked"
  status: "Active" | "Idle" | "Blocked"; 
  orders: number;
}

// 🌟 NEW: The function that calls FastAPI
export const getFactoryStatus = async (): Promise<FactoryLine[]> => {
  const response = await apiClient.get("/api/factory/status");
  return response.data;
};

// 🌟 NEW: The shape of a single phone call record
export interface AuditRecord {
  call_id: number;
  line_id: string;
  supervisor: string;
  status: string;
  start_time: string;
  sentiment: "positive" | "neutral" | "negative" | "frustrated" | "pending";
  unresolved_issues: string[];
  transcript: { user: string; ai: string }[];
}

// 🌟 NEW: The function to fetch the audit trail
export const getAuditTrail = async (): Promise<AuditRecord[]> => {
  const response = await apiClient.get("/api/audit-trail");
  return response.data;
};

// 🌟 NEW: The shapes for our POST request (matching your Python DTOs)
export interface OrderSubmit {
  order_sequence: number;
  order_name: string;
}

export interface DailySchedule {
  line_id: string;
  supervisor_name: string;
  supervisor_phone: string;
  orders: OrderSubmit[];
}

// 🌟 NEW: The mutation function to push data to FastAPI
export const uploadSchedule = async (schedule: DailySchedule) => {
  const response = await apiClient.post("/api/schedule/upload", schedule);
  return response.data;
};

// 🌟 NEW: Trigger a manual Twilio call
export const triggerManualCall = async (lineId: string) => {
  const response = await apiClient.post(`/api/factory/call/${lineId}`);
  return response.data;
};