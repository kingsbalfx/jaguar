// lib/openai_prompts.js
export const HELP_PROMPTS = {
  general: (context) =>
    `You are KINGSBALFX assistant. Help the user with clear, concise steps. Context: ${context}`,

  troubleshoot: (code, error) =>
    `You are a senior developer. Help troubleshoot this code and error. Code: ${code} Error: ${error}`,
};
