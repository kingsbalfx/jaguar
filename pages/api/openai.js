// lib/openai.js
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function askOpenAI(prompt) {
  try {
    const response = await client.chat.completions.create({
      model: "gpt-3.5-turbo", // or "gpt-4o-mini" if you want
      messages: [{ role: "user", content: prompt }],
      max_tokens: 500,
    });

    return { answer: response.choices[0].message.content.trim() };
  } catch (error) {
    console.error("OpenAI API error:", error);
    throw new Error("Failed to fetch response from OpenAI");
  }
}
