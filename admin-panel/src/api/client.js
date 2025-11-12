import axios from "axios";

const defaultBaseUrl = import.meta.env.VITE_API_BASE_URL || "";

export const api = axios.create({
  baseURL: defaultBaseUrl,
  timeout: 10000
});

export async function checkHealth() {
  const response = await api.get("/health");
  return response.data;
}

export async function fetchStudentByParticipant(participantId) {
  const response = await api.get(`/students/by-participant/${encodeURIComponent(participantId)}`);
  return response.data;
}

export async function fetchStudents({ limit = 50, offset = 0 } = {}) {
  const response = await api.get("/students", {
    params: { limit, offset }
  });
  return response.data;
}

export async function fetchEvents({ limit = 50 } = {}) {
  const response = await api.get("/events/active", {
    params: { limit }
  });
  return response.data;
}

export async function fetchEventsBulk(ids) {
  if (!ids?.length) {
    return { events: [], total: 0 };
  }
  const response = await api.post("/events/bulk", { ids });
  return response.data;
}

export async function fetchRecommendationsByStudent(studentId, { limit = 10 } = {}) {
  const response = await api.get(`/recommendations/by-student/${encodeURIComponent(studentId)}`, {
    params: { limit }
  });
  return response.data;
}

export async function recalculateRecommendationsForStudent(studentId, { minScore = 0 } = {}) {
  const response = await api.post(
    `/recommendations/by-student/${encodeURIComponent(studentId)}/recalculate`,
    null,
    {
      params: { min_score: minScore }
    }
  );
  return response.data;
}

