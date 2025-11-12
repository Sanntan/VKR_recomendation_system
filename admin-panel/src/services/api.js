import axios from "axios";

const baseURL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

const client = axios.create({
  baseURL,
  timeout: 15000,
});

export default {
  async healthCheck() {
    const { data } = await client.get("/health");
    return data;
  },

  async getActiveEvents(limit = 50) {
    const { data } = await client.get("/events/active", {
      params: { limit },
    });
    return data;
  },

  async getEventsByCluster(clusterId, limit = 50) {
    const { data } = await client.get("/events/by-clusters", {
      params: { cluster_ids: clusterId, limit },
    });
    return data;
  },

  async getEventsBulk(ids) {
    const { data } = await client.post("/events/bulk", { ids });
    return data;
  },

  async getStudentByParticipant(participantId) {
    const { data } = await client.get(
      `/students/by-participant/${encodeURIComponent(participantId)}`
    );
    return data;
  },

  async getRecommendations(studentId, limit = 10) {
    const { data } = await client.get(
      `/recommendations/by-student/${studentId}`,
      { params: { limit } }
    );
    return data;
  },

  async recalculateRecommendations(minScore = 0) {
    const { data } = await client.post("/recommendations/recalculate", {
      min_score: minScore,
    });
    return data;
  },
};


