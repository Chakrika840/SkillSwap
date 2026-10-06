import api from "./client";

export const getTestStatus = (skillId) =>
  api.get(`/api/skill-tests/skills/${skillId}/status`).then((r) => r.data);

// Generating questions the first time for a skill can take ~10-30 seconds.
export const startTest = (skillId) =>
  api.post(`/api/skill-tests/skills/${skillId}/start`, null, { timeout: 120000 }).then((r) => r.data);

export const submitTest = (testId, answers) =>
  api.post(`/api/skill-tests/${testId}/submit`, { answers }).then((r) => r.data);

export const getTestResult = (testId) =>
  api.get(`/api/skill-tests/${testId}/result`).then((r) => r.data);
