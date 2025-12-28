import openai

class OpenAILLM:
    def __init__(self, api_key=None, base_url="http://localhost:11434/v1", model="starcoder2:3b"):
        """
        Local Ollama wrapper using OpenAI-compatible API.
        No real API key needed — Ollama ignores it.
        """
        self.client = openai.OpenAI(
            api_key = api_key or "unused",  # Dummy key
            base_url = base_url
        )
        self.model = model
        self.message_history = []

    def query_llm(self, system_prompt, user_query, model=None, max_tokens=4096, temperature=0.7):
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Handle single string or list of user queries
            queries = user_query if isinstance(user_query, list) else [user_query]
            for q in queries:
                messages.append({"role": "user", "content": q})

            # Use conversation history for multi-turn (error feedback)
            full_messages = self.message_history + messages

            response = self.client.chat.completions.create(
                model=model or self.model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            reply = response.choices[0].message.content.strip()

            # Update history for next turn
            self.message_history.extend(messages)
            self.message_history.append({"role": "assistant", "content": reply})

            return reply

        except Exception as e:
            return f"Local LLM Error: {str(e)}"
