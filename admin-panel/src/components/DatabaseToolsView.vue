<template>
  <section class="card maintenance-card">
    <header class="card-header">
      <div>
        <h2>Управление данными</h2>
        <p>Интерфейс для операций обработки данных и обслуживания базы</p>
      </div>
    </header>

    <div class="maintenance-grid">
      <article class="section-card">
        <header>
          <h3>Мероприятия</h3>
          <p>Обработка CSV, генерация JSON и загрузка в БД</p>
        </header>

        <div class="section-block">
          <div class="block-header">
            <h4>Обработка CSV → JSON</h4>
            <p v-if="info" class="file-hint">
              По умолчанию: <code>{{ info.eventsInputFile }}</code> → <code>{{ info.eventsOutputFile }}</code>
            </p>
          </div>

          <div class="file-input-group">
            <label class="file-label">
              <span>CSV файл</span>
              <div class="file-selector">
                <button type="button" class="btn-select" @click="() => csvFileInput?.click()">
                  {{ csvFile ? csvFile.name : "Выбрать файл" }}
                </button>
                <input
                  ref="csvFileInput"
                  type="file"
                  accept=".csv"
                  style="display: none"
                  @change="handleCsvFileSelect"
                />
              </div>
            </label>
          </div>

          <div class="actions">
            <button type="button" @click="handleProcessCsv" :disabled="loading.processCsv">
              {{ loading.processCsv ? "Обработка..." : "Обработать CSV" }}
            </button>
          </div>

          <ResultBlock :result="results.processCsv" :error="errors.processCsv" />
        </div>

        <div class="section-block">
          <div class="block-header">
            <h4>Загрузка JSON в БД</h4>
            <p v-if="info" class="file-hint">
              По умолчанию: <code>{{ info.eventsOutputFile }}</code>
            </p>
          </div>

          <div class="file-input-group">
            <label class="file-label">
              <span>JSON файл</span>
              <div class="file-selector">
                <button type="button" class="btn-select" @click="() => jsonFileInput?.click()">
                  {{ jsonFile ? jsonFile.name : "Выбрать файл" }}
                </button>
                <input
                  ref="jsonFileInput"
                  type="file"
                  accept=".json"
                  style="display: none"
                  @change="handleJsonFileSelect"
                />
              </div>
            </label>
          </div>

          <div class="form-row">
            <label class="checkbox">
              <input type="checkbox" v-model="assignClusters" />
              <span>Привязывать кластеры мероприятий</span>
            </label>
          </div>

          <div class="form-row" v-if="assignClusters">
            <label>
              <span>Top-K кластеров</span>
              <input type="number" v-model.number="clusterTopK" min="1" />
            </label>
            <label>
              <span>Порог схожести</span>
              <input type="number" v-model.number="similarityThreshold" min="0" max="1" step="0.01" />
            </label>
          </div>

          <div class="actions">
            <button type="button" @click="handleLoadEvents" :disabled="loading.loadEvents">
              {{ loading.loadEvents ? "Загрузка..." : "Загрузить в БД" }}
            </button>
          </div>

          <ResultBlock :result="results.loadEvents" :error="errors.loadEvents" />
        </div>

        <div class="section-block">
          <div class="block-header">
            <h4>Пересчёт рекомендаций</h4>
          </div>

          <div class="form-row">
            <label>
              <span>Минимальный score</span>
              <input type="number" v-model.number="minScore" min="0" max="1" step="0.01" />
            </label>
            <label>
              <span>Batch size</span>
              <input type="number" v-model.number="batchSize" min="1" />
            </label>
          </div>

          <div class="actions">
            <button type="button" @click="handleRecalculate" :disabled="loading.recalculate">
              {{ loading.recalculate ? "Пересчёт..." : "Пересчитать" }}
            </button>
          </div>

          <ResultBlock :result="results.recalculate" :error="errors.recalculate" />
        </div>
      </article>

      <article class="section-card">
        <header>
          <h3>Направления</h3>
          <p>Предобработка Excel и кластеризация направлений</p>
        </header>

        <div class="section-block">
          <div class="block-header">
            <h4>Предобработка Excel</h4>
            <p v-if="info" class="file-hint">
              По умолчанию: <code>{{ info.directionsInputFile }}</code> → <code>{{ info.directionsOutputFile }}</code>
            </p>
          </div>

          <div class="file-input-group">
            <label class="file-label">
              <span>Excel файл</span>
              <div class="file-selector">
                <button type="button" class="btn-select" @click="() => excelFileInput?.click()">
                  {{ excelFile ? excelFile.name : "Выбрать файл" }}
                </button>
                <input
                  ref="excelFileInput"
                  type="file"
                  accept=".xlsx,.xls"
                  style="display: none"
                  @change="handleExcelFileSelect"
                />
              </div>
            </label>
          </div>

          <div class="actions">
            <button type="button" @click="handlePreprocessDirections" :disabled="loading.preprocess">
              {{ loading.preprocess ? "Обработка..." : "Предобработать" }}
            </button>
          </div>

          <ResultBlock :result="results.preprocess" :error="errors.preprocess" />
        </div>

        <div class="section-block">
          <div class="block-header">
            <h4>Кластеризация направлений</h4>
          </div>

          <div class="form-row">
            <label class="checkbox">
              <input type="checkbox" v-model="forcePreprocess" />
              <span>Выполнить предобработку перед кластеризацией</span>
            </label>
          </div>

          <div class="actions">
            <button type="button" @click="handleClusterizeDirections" :disabled="loading.clusterize">
              {{ loading.clusterize ? "Кластеризация..." : "Запустить кластеризацию" }}
            </button>
          </div>

          <ResultBlock :result="results.clusterize" :error="errors.clusterize" />
        </div>
      </article>

      <article class="section-card">
        <header>
          <h3>Студенты</h3>
          <p>Обработка Excel, генерация JSON и загрузка в БД</p>
        </header>

        <div class="section-block">
          <div class="block-header">
            <h4>Обработка Excel → JSON</h4>
            <p v-if="info" class="file-hint">
              По умолчанию: <code>{{ info.studentsInputFile }}</code> → <code>{{ info.studentsOutputFile }}</code>
            </p>
          </div>

          <div class="file-input-group">
            <label class="file-label">
              <span>Excel файл</span>
              <div class="file-selector">
                <button type="button" class="btn-select" @click="() => studentsExcelFileInput?.click()">
                  {{ studentsExcelFile ? studentsExcelFile.name : "Выбрать файл" }}
                </button>
                <input
                  ref="studentsExcelFileInput"
                  type="file"
                  accept=".xlsx,.xls"
                  style="display: none"
                  @change="handleStudentsExcelFileSelect"
                />
              </div>
            </label>
          </div>

          <div class="actions">
            <button type="button" @click="handleProcessStudentsExcel" :disabled="loading.processStudentsExcel">
              {{ loading.processStudentsExcel ? "Обработка..." : "Обработать Excel" }}
            </button>
          </div>

          <ResultBlock :result="results.processStudentsExcel" :error="errors.processStudentsExcel" />
        </div>

        <div class="section-block">
          <div class="block-header">
            <h4>Загрузка JSON в БД</h4>
            <p v-if="info" class="file-hint">
              По умолчанию: <code>{{ info.studentsOutputFile }}</code>
            </p>
          </div>

          <div class="file-input-group">
            <label class="file-label">
              <span>JSON файл</span>
              <div class="file-selector">
                <button type="button" class="btn-select" @click="() => studentsJsonFileInput?.click()">
                  {{ studentsJsonFile ? studentsJsonFile.name : "Выбрать файл" }}
                </button>
                <input
                  ref="studentsJsonFileInput"
                  type="file"
                  accept=".json"
                  style="display: none"
                  @change="handleStudentsJsonFileSelect"
                />
              </div>
            </label>
          </div>

          <div class="form-row">
            <label>
              <span>Учебное заведение</span>
              <input type="text" v-model="defaultInstitution" placeholder="ФГАОУ ВО «ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ» (ТюмГУ)"/>
            </label>
            <label>
              <span>Лимит студентов</span>
              <input type="number" v-model.number="studentsLimit" min="1" placeholder="Без ограничений" />
              <small style="color: #6c757d; font-size: 0.8rem;">Оставьте пустым для загрузки всех</small>
            </label>
          </div>

          <div class="actions">
            <button type="button" @click="handleLoadStudents" :disabled="loading.loadStudents">
              {{ loading.loadStudents ? "Загрузка..." : "Загрузить в БД" }}
            </button>
          </div>

          <ResultBlock :result="results.loadStudents" :error="errors.loadStudents" />
        </div>
      </article>

      <article class="section-card warning">
        <header>
          <h3>Сброс базы данных</h3>
          <p>Полная очистка всех таблиц</p>
        </header>

        <div class="section-block">
          <p class="warning-text">
            Операция необратима. Введите <code>RESET</code> для подтверждения.
          </p>

          <div class="form-row">
            <label>
              <span>Подтверждение</span>
              <input
                type="text"
                v-model="resetConfirmation"
                placeholder="Введите RESET"
              />
            </label>
          </div>

          <div class="actions">
            <button
              type="button"
              class="danger"
              :disabled="loading.reset || resetConfirmation !== 'RESET'"
              @click="handleResetDatabase"
            >
              {{ loading.reset ? "Сброс..." : "Сбросить БД" }}
            </button>
          </div>

          <ResultBlock :result="results.reset" :error="errors.reset" />
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { defineComponent, h, onMounted, reactive, ref } from "vue";

import {
  fetchMaintenanceInfo,
  maintenanceClusterizeDirections,
  maintenanceLoadEventsFromJson,
  maintenancePreprocessDirections,
  maintenanceProcessEventsCsv,
  maintenanceResetDatabase,
  recalculateRecommendationsGlobal,
  maintenanceProcessStudentsExcel,
  maintenanceLoadStudentsFromJson
} from "../api/client.js";

const ResultBlock = defineComponent({
  name: "ResultBlock",
  props: {
    result: {
      type: Object,
      default: null
    },
    error: {
      type: Object,
      default: null
    }
  },
  setup(props) {
    return () => {
      if (!props.result && !props.error) {
        return null;
      }

      const resultDetails =
        props.result?.details?.length &&
        h(
          "ul",
          { class: "details-list" },
          props.result.details.map((item) =>
            h("li", { key: item.label }, [
              `${item.label}: `,
              item.value ? h("code", item.value) : h("span", "—")
            ])
          )
        );

      const resultMessage =
        props.result &&
        h(
          "div",
          { class: "result-message success" },
          [h("strong", props.result.message), resultDetails].filter(Boolean)
        );

      const errorMessage =
        props.error &&
        h("div", { class: "result-message error" }, [h("strong", props.error.message)]);

      const logContent = props.result?.log || props.error?.log;
      const logNode = logContent ? h("pre", { class: "log-output" }, logContent) : null;

      return h(
        "div",
        { class: "result-container" },
        [resultMessage, errorMessage, logNode].filter(Boolean)
      );
    };
  }
});

const info = ref(null);

const loading = reactive({
  processCsv: false,
  loadEvents: false,
  recalculate: false,
  preprocess: false,
  clusterize: false,
  processStudentsExcel: false,
  loadStudents: false,
  reset: false
});

const results = reactive({
  processCsv: null,
  loadEvents: null,
  recalculate: null,
  preprocess: null,
  clusterize: null,
  processStudentsExcel: null,
  loadStudents: null,
  reset: null
});

const errors = reactive({
  processCsv: null,
  loadEvents: null,
  recalculate: null,
  preprocess: null,
  clusterize: null,
  processStudentsExcel: null,
  loadStudents: null,
  reset: null
});

const assignClusters = ref(false);
const clusterTopK = ref(null);
const similarityThreshold = ref(null);

const minScore = ref(0);
const batchSize = ref(1000);

const forcePreprocess = ref(false);

const resetConfirmation = ref("");

// Файлы и ссылки на input элементы
const csvFile = ref(null);
const csvFileInput = ref(null);

const jsonFile = ref(null);
const jsonFileInput = ref(null);

const excelFile = ref(null);
const excelFileInput = ref(null);

const studentsExcelFile = ref(null);
const studentsExcelFileInput = ref(null);

const studentsJsonFile = ref(null);
const studentsJsonFileInput = ref(null);

const defaultInstitution = ref("ФГАОУ ВО «ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ» (ТюмГУ)");
const studentsLimit = ref(null);

function handleCsvFileSelect(event) {
  csvFile.value = event.target.files[0] || null;
}

function handleJsonFileSelect(event) {
  jsonFile.value = event.target.files[0] || null;
}

function handleExcelFileSelect(event) {
  excelFile.value = event.target.files[0] || null;
}

function handleStudentsExcelFileSelect(event) {
  studentsExcelFile.value = event.target.files[0] || null;
}

function handleStudentsJsonFileSelect(event) {
  studentsJsonFile.value = event.target.files[0] || null;
}

function extractError(error) {
  if (error?.response?.data?.detail) {
    const detail = error.response.data.detail;
    if (typeof detail === "string") {
      return { message: detail };
    }
    if (detail?.message) {
      return { message: detail.message, log: detail.log || null };
    }
  }
  return { message: error?.message || "Неизвестная ошибка" };
}

function clearResult(key) {
  results[key] = null;
  errors[key] = null;
}

function setResult(key, value) {
  results[key] = value;
  errors[key] = null;
}

function setError(key, error) {
  errors[key] = extractError(error);
  results[key] = null;
}

async function loadInfo() {
  try {
    const response = await fetchMaintenanceInfo();
    info.value = {
      eventsInputFile: response.events_input_file ?? response.eventsInputFile,
      eventsOutputFile: response.events_output_file ?? response.eventsOutputFile,
      directionsInputFile: response.directions_input_file ?? response.directionsInputFile,
      directionsOutputFile: response.directions_output_file ?? response.directionsOutputFile,
      studentsInputFile: response.students_input_file ?? response.studentsInputFile,
      studentsOutputFile: response.students_output_file ?? response.studentsOutputFile,
      clusterTopKDefault: response.cluster_top_k_default ?? response.clusterTopKDefault ?? 3,
      similarityThresholdDefault:
        response.similarity_threshold_default ?? response.similarityThresholdDefault ?? 0.35
    };

    if (clusterTopK.value === null) {
      clusterTopK.value = info.value.clusterTopKDefault;
    }
    if (similarityThreshold.value === null) {
      similarityThreshold.value = info.value.similarityThresholdDefault;
    }
  } catch (error) {
    console.error("Failed to load maintenance info:", error);
  }
}

async function handleProcessCsv() {
  loading.processCsv = true;
  clearResult("processCsv");
  try {
    const response = await maintenanceProcessEventsCsv({
      file: csvFile.value,
      inputFile: undefined,
      outputFile: undefined
    });
    setResult("processCsv", {
      message: `Обработано мероприятий: ${response.processed}`,
      log: response.log,
      details: [
        { label: "CSV", value: response.input_file ?? response.inputFile },
        { label: "JSON", value: response.output_file ?? response.outputFile }
      ]
    });
    csvFile.value = null;
    if (csvFileInput.value) csvFileInput.value.value = "";
  } catch (error) {
    setError("processCsv", error);
  } finally {
    loading.processCsv = false;
  }
}

async function handleLoadEvents() {
  loading.loadEvents = true;
  clearResult("loadEvents");
  try {
    const response = await maintenanceLoadEventsFromJson({
      file: jsonFile.value,
      inputFile: undefined,
      assignClusters: assignClusters.value,
      clusterTopK: assignClusters.value ? clusterTopK.value : undefined,
      similarityThreshold: assignClusters.value ? similarityThreshold.value : undefined
    });
    setResult("loadEvents", {
      message: `Вставлено ${response.added}, пропущено ${response.skipped} из ${response.total_in_file}`,
      log: response.log,
      details: [
        { label: "JSON", value: response.output_file ?? response.outputFile },
        { label: "Привязка кластеров", value: response.assign_clusters ? "Да" : "Нет" },
        { label: "Top-K", value: response.cluster_top_k },
        { label: "Порог", value: response.similarity_threshold }
      ]
    });
    jsonFile.value = null;
    if (jsonFileInput.value) jsonFileInput.value.value = "";
  } catch (error) {
    setError("loadEvents", error);
  } finally {
    loading.loadEvents = false;
  }
}

async function handleRecalculate() {
  loading.recalculate = true;
  clearResult("recalculate");
  try {
    const response = await recalculateRecommendationsGlobal({
      minScore: minScore.value,
      batchSize: batchSize.value
    });
    const stats = response.stats || response;
    const summary = Object.entries(stats || {})
      .map(([key, value]) => `${key}: ${value}`)
      .join(", ");
    setResult("recalculate", {
      message: `Пересчёт выполнен. ${summary || "Без статистики"}`,
      log: response.log || null,
      details: null
    });
  } catch (error) {
    setError("recalculate", error);
  } finally {
    loading.recalculate = false;
  }
}

async function handlePreprocessDirections() {
  loading.preprocess = true;
  clearResult("preprocess");
  try {
    const response = await maintenancePreprocessDirections({
      file: excelFile.value,
      inputFile: undefined,
      outputFile: undefined
    });
    setResult("preprocess", {
      message: `Строк: ${response.rows}, столбцов: ${response.columns}`,
      log: response.log,
      details: [
        { label: "Исходный файл", value: response.input_file ?? response.inputFile },
        { label: "Результат", value: response.output_file ?? response.outputFile }
      ]
    });
    excelFile.value = null;
    if (excelFileInput.value) excelFileInput.value.value = "";
  } catch (error) {
    setError("preprocess", error);
  } finally {
    loading.preprocess = false;
  }
}

async function handleClusterizeDirections() {
  loading.clusterize = true;
  clearResult("clusterize");
  try {
    const response = await maintenanceClusterizeDirections({
      forcePreprocess: forcePreprocess.value
    });
    setResult("clusterize", {
      message: response.message || "Кластеризация выполнена",
      log: response.log,
      details: null
    });
  } catch (error) {
    setError("clusterize", error);
  } finally {
    loading.clusterize = false;
  }
}

async function handleProcessStudentsExcel() {
  loading.processStudentsExcel = true;
  clearResult("processStudentsExcel");
  try {
    const response = await maintenanceProcessStudentsExcel({
      file: studentsExcelFile.value,
      inputFile: undefined,
      outputFile: undefined
    });
    setResult("processStudentsExcel", {
      message: `Обработано студентов: ${response.processed}`,
      log: response.log,
      details: [
        { label: "Excel", value: response.input_file ?? response.inputFile },
        { label: "JSON", value: response.output_file ?? response.outputFile }
      ]
    });
    studentsExcelFile.value = null;
    if (studentsExcelFileInput.value) studentsExcelFileInput.value.value = "";
  } catch (error) {
    setError("processStudentsExcel", error);
  } finally {
    loading.processStudentsExcel = false;
  }
}

async function handleLoadStudents() {
  loading.loadStudents = true;
  clearResult("loadStudents");
  try {
    const response = await maintenanceLoadStudentsFromJson({
      file: studentsJsonFile.value,
      inputFile: undefined,
      defaultInstitution: defaultInstitution.value,
      limit: studentsLimit.value && studentsLimit.value > 0 ? studentsLimit.value : undefined
    });
    const limitText = studentsLimit.value && studentsLimit.value > 0 ? ` (лимит: ${studentsLimit.value})` : "";
    setResult("loadStudents", {
      message: `Вставлено ${response.added}, пропущено ${response.skipped} из ${response.total_in_file}${limitText}`,
      log: response.log,
      details: [
        { label: "JSON", value: response.output_file ?? response.outputFile },
        { label: "Учебное заведение", value: defaultInstitution.value },
        { label: "Лимит", value: studentsLimit.value && studentsLimit.value > 0 ? studentsLimit.value.toString() : "Без ограничений" }
      ]
    });
    studentsJsonFile.value = null;
    if (studentsJsonFileInput.value) studentsJsonFileInput.value.value = "";
  } catch (error) {
    setError("loadStudents", error);
  } finally {
    loading.loadStudents = false;
  }
}

async function handleResetDatabase() {
  if (resetConfirmation.value !== "RESET") {
    errors.reset = { message: "Введите RESET для подтверждения операции" };
    return;
  }

  loading.reset = true;
  clearResult("reset");
  try {
    const response = await maintenanceResetDatabase({ confirm: true });
    setResult("reset", {
      message: response.message || "База данных сброшена",
      log: response.log,
      details: null
    });
    resetConfirmation.value = "";
  } catch (error) {
    setError("reset", error);
  } finally {
    loading.reset = false;
  }
}

onMounted(() => {
  loadInfo();
});
</script>

<style scoped>
.maintenance-card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.maintenance-card code {
  font-family: "Fira Code", "Consolas", "SFMono-Regular", monospace;
  background: #f1f3f5;
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
  font-size: 0.85rem;
}

.maintenance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 1.5rem;
}

.section-card {
  border: 1px solid #dee2e6;
  border-radius: 12px;
  background: #ffffff;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}

.section-card.warning {
  border-color: #f5c2c7;
  background: #fff5f5;
}

.section-card > header h3 {
  margin: 0 0 0.3rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.section-card > header p {
  margin: 0;
  color: #6c757d;
  font-size: 0.9rem;
}

.section-block {
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 1rem;
  background: #f8f9fa;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.section-card.warning .section-block {
  background: #fff0f0;
  border-color: #f5c2c7;
}

.block-header h4 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.block-header p {
  margin: 0;
  color: #6c757d;
  font-size: 0.85rem;
}

.file-hint {
  margin-top: 0.25rem;
}

.file-input-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.file-label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: #495057;
}

.file-selector {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.btn-select {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid #ced4da;
  background: #ffffff;
  color: #212529;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
  flex: 1;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-select:hover {
  background: #f8f9fa;
  border-color: #adb5bd;
}

.form-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  align-items: flex-start;
}

.form-row label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: #495057;
  flex: 1;
  min-width: 120px;
}

.form-row label.checkbox {
  flex-direction: row;
  align-items: flex-start;
  flex: 0 1 auto;
  min-width: auto;
}

.form-row input[type="number"],
.form-row input[type="text"] {
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  border: 1px solid #ced4da;
  background: #ffffff;
  color: #212529;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  font-size: 0.9rem;
}

.form-row input[type="number"]:focus,
.form-row input[type="text"]:focus {
  outline: none;
  border-color: #0d6efd;
  box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.1);
}

.checkbox {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: #495057;
}

.checkbox input {
  width: 18px;
  height: 18px;
  min-width: 18px;
  margin-top: 0.1rem;
  cursor: pointer;
  flex-shrink: 0;
}

.checkbox span {
  line-height: 1.5;
  flex: 1;
}

.actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.actions button {
  padding: 0.6rem 1.25rem;
  border-radius: 8px;
  border: none;
  background: #0d6efd;
  color: #ffffff;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.actions button:hover:not(:disabled) {
  background: #0b5ed7;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(13, 110, 253, 0.25);
}

.actions button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.actions button.danger {
  background: #dc3545;
}

.actions button.danger:hover:not(:disabled) {
  background: #bb2d3b;
  box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);
}

.warning-text {
  margin: 0;
  color: #b02a37;
  font-weight: 500;
  font-size: 0.9rem;
}

.result-container {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-top: 0.5rem;
}

.result-message {
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
}

.result-message.success {
  background: #d1e7dd;
  border: 1px solid #badbcc;
  color: #0f5132;
}

.result-message.error {
  background: #f8d7da;
  border: 1px solid #f5c2c7;
  color: #842029;
}

.details-list {
  margin: 0.5rem 0 0 0;
  padding-left: 1.1rem;
  color: #495057;
  font-size: 0.85rem;
}

.details-list code {
  background: rgba(13, 110, 253, 0.12);
  padding: 0 0.25rem;
  border-radius: 4px;
}

.log-output {
  background: #212529;
  color: #f8f9fa;
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 0.8rem;
  border-radius: 8px;
  padding: 0.75rem;
  white-space: pre-wrap;
  max-height: 220px;
  overflow-y: auto;
  margin-top: 0.5rem;
}

@media (max-width: 768px) {
  .maintenance-grid {
    grid-template-columns: 1fr;
  }
}
</style>
