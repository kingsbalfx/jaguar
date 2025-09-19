// pages/api/openai/help.js
import { HELP_PROMPTS } from "../../../lib/openai_prompts";
import { askOpenAI } from "../../../lib/openai";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { context } = req.body;

    if (!context) {
      return res.status(400).json({ error: "Missing context" });
    }

    const prompt = HELP_PROMPTS.general(context);
    const response = await askOpenAI(prompt);

    res.status(200).json({ result: response.answer });
  } catch (error) {
    console.error("Help API Error:", error);
    res.status(500).json({ error: "Internal Server Error" });
  }
}
