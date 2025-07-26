import openai, ollama, os
import time


# how to define a client for OpenAI and Ollama
# openai_client = openai.OpenAI(
#     api_key=os.environ.get("OPENAI_API_KEY"),
# )
# ollama_client = ollama.Client(
#     host="http://192.168.29.2:11434/"
# )


# system_prompt = "Always talk in haiku."
# prompt = "What colour is the sky?"


# # how to get a response from OpenAI and Ollama
# response = openai_client.responses.create(
#     model="gpt-4.1-nano",
#     instructions=system_prompt,
#     input=prompt,
# )
# print(response.output_text)

# response = ollama_client.generate(
#     model="gemma3:latest",
#     system=system_prompt,
#     prompt=prompt
# )
# print(response.response)


class Models:
    def __init__(self):
        self.models = [
            {"name": "gpt-4.1-nano", "type": "openai"},
            {"name": "gpt-4.1-mini", "type": "openai"},
            {"name": "gpt-4o-mini",  "type": "openai"},
        ]
        self.fallback_model = {"name": "gemma3:latest", "type": "ollama"}
        self.interval = 20
        self.last_model = -1
        self.last_time = 0  # time.time()
        self.num_retries = 2
        self.fallback_until = 0
        self.openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.ollama_client = ollama.Client(host="http://192.168.29.2:11434/")

    def _generate_model_response(self, model, system_prompt, prompt):
        now = int(time.time())
        if now < self.last_time+self.interval:  # Wait if interval hasn't passed
            wait_time = self.last_time + self.interval - now + 1
            time.sleep(wait_time)

        if model["type"] == "ollama":
            return self.ollama_client.generate(
                model=model["name"],
                system=system_prompt,
                prompt=prompt
            ).response
        elif model["type"] == "openai":
            return self.openai_client.responses.create(
                model=model["name"],
                instructions=system_prompt,
                input=prompt
            ).output_text

        raise ValueError(f"Unknown model type: {model['type']}")

    def get_response(self, system_prompt, prompt):
        now = int(time.time())
        if now < self.fallback_until:
            return self._generate_model_response(self.fallback_model, system_prompt, prompt)

        # Rotate model
        self.last_model = (self.last_model + 1) % len(self.models)
        self.last_time = now

        # Try each model up to num_retries times
        for retry in range(self.num_retries * len(self.models)):
            model_idx = (self.last_model + retry) % len(self.models)
            model = self.models[model_idx]
            try:
                result = self._generate_model_response(model, system_prompt, prompt)
                self.last_model = model_idx
                self.last_time = time.time()
                print(f"Model {model['name']} succeeded.")
                return result
            except openai.RateLimitError as e:
                print(f"Model {model['name']} rate limited")
            except Exception as e:
                print(f"Model {model['name']} failed: {e.__class__.__name__} - {e}")
                continue
        # If all retries fail, activate fallback for 5 minutes
        self.fallback_until = time.time() + 300
        return self._generate_model_response(self.fallback_model, system_prompt, prompt)


# print(get_response("Always talk in haiku.", "What colour is the sky?"))
