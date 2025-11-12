import axios from "axios";

const defaultBaseUrl = import.meta.env.VITE_API_BASE_URL || "";

// Обычный клиент для быстрых операций (10 секунд)
export const api = axios.create({
  baseURL: defaultBaseUrl,
  timeout: 10000
});

// Клиент для долгих операций (maintenance, ML модели, кластеризация) - 10 минут
export const maintenanceApi = axios.create({
  baseURL: defaultBaseUrl,
  timeout: 600000 // 10 минут для операций с ML моделями и кластеризацией
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

export async function fetchFavoritesByStudent(studentId, { limit = 100 } = {}) {
  const url = `/favorites/by-student/${encodeURIComponent(studentId)}`;
  console.log("API: fetchFavoritesByStudent - URL:", url, "limit:", limit);
  try {
    const response = await api.get(url, {
      params: { limit }
    });
    console.log("API: fetchFavoritesByStudent - Response:", response);
    return response.data;
  } catch (error) {
    console.error("API: fetchFavoritesByStudent - Error:", error);
    throw error;
  }
}

export async function getFavoritesCount(studentId) {
  const url = `/favorites/by-student/${encodeURIComponent(studentId)}/count`;
  console.log("API: getFavoritesCount - URL:", url);
  try {
    const response = await api.get(url);
    console.log("API: getFavoritesCount - Response:", response);
    return response.data;
  } catch (error) {
    console.error("API: getFavoritesCount - Error:", error);
    throw error;
  }
}

export async function addFavorite(studentId, eventId) {
  const response = await api.post(`/favorites/${encodeURIComponent(studentId)}/${encodeURIComponent(eventId)}`);
  return response.data;
}

export async function removeFavorite(studentId, eventId) {
  await api.delete(`/favorites/${encodeURIComponent(studentId)}/${encodeURIComponent(eventId)}`);
}

export async function checkFavorite(studentId, eventId) {
  const response = await api.get(`/favorites/${encodeURIComponent(studentId)}/${encodeURIComponent(eventId)}/check`);
  return response.data;
}

export async function recalculateRecommendationsGlobal({ minScore = 0, batchSize = 1000 } = {}) {
  const response = await maintenanceApi.post("/maintenance/recommendations/recalculate", {
    min_score: minScore,
    batch_size: batchSize
  });
  return response.data;
}

export async function fetchMaintenanceInfo() {
  const response = await api.get("/maintenance/info"); // Быстрая операция, используем обычный клиент
  return response.data;
}

export async function maintenanceProcessEventsCsv({ file, inputFile, outputFile } = {}) {
  if (file) {
    // Если есть файл, используем multipart/form-data
    const formData = new FormData();
    formData.append("file", file);
    if (inputFile) {
      formData.append("input_file", inputFile);
    }
    if (outputFile) {
      formData.append("output_file", outputFile);
    }
    const response = await maintenanceApi.post("/maintenance/events/process-csv", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return response.data;
  } else {
    // Если файла нет, используем JSON
    const response = await maintenanceApi.post("/maintenance/events/process-csv", {
      input_file: inputFile || null,
      output_file: outputFile || null
    });
    return response.data;
  }
}

export async function maintenanceLoadEventsFromJson({
  file,
  inputFile,
  assignClusters = false,
  clusterTopK,
  similarityThreshold
} = {}) {
  if (file) {
    // Если есть файл, используем multipart/form-data
    const formData = new FormData();
    formData.append("file", file);
    if (inputFile) {
      formData.append("input_file", inputFile);
    }
    formData.append("assign_clusters", assignClusters);
    if (clusterTopK != null) {
      formData.append("cluster_top_k", clusterTopK);
    }
    if (similarityThreshold != null) {
      formData.append("similarity_threshold", similarityThreshold);
    }
    const response = await maintenanceApi.post("/maintenance/events/load-json", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return response.data;
  } else {
    // Если файла нет, используем JSON
    const response = await maintenanceApi.post("/maintenance/events/load-json", {
      input_file: inputFile || null,
      assign_clusters: assignClusters,
      cluster_top_k: clusterTopK || null,
      similarity_threshold: similarityThreshold || null
    });
    return response.data;
  }
}

export async function maintenancePreprocessDirections({ file, inputFile, outputFile } = {}) {
  if (file) {
    // Если есть файл, используем multipart/form-data
    const formData = new FormData();
    formData.append("file", file);
    if (inputFile) {
      formData.append("input_file", inputFile);
    }
    if (outputFile) {
      formData.append("output_file", outputFile);
    }
    const response = await maintenanceApi.post("/maintenance/directions/preprocess", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return response.data;
  } else {
    // Если файла нет, используем JSON
    const response = await maintenanceApi.post("/maintenance/directions/preprocess", {
      input_file: inputFile || null,
      output_file: outputFile || null
    });
    return response.data;
  }
}

export async function maintenanceClusterizeDirections({ forcePreprocess = false } = {}) {
  const response = await maintenanceApi.post("/maintenance/directions/clusterize", {
    force_preprocess: forcePreprocess
  });
  return response.data;
}

export async function maintenanceResetDatabase({ confirm }) {
  const response = await maintenanceApi.post("/maintenance/database/reset", { confirm });
  return response.data;
}

