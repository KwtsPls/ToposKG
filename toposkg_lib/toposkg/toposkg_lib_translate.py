import os
os.environ["WANDB_DISABLED"] = "true"

from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template

class ToposkgLibTranslator:
    def __init__(self):
        # Your model name on Hugging Face
        model_name = "SKefalidis/gemma3-12b-4bit-translation"

        # Load the base model with LoRA
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=2048,
            dtype=None,  # Set to torch.float16 or bfloat16 if needed
            load_in_4bit=True,  # or False if not using 4-bit quantization
        )

        tokenizer = get_chat_template(
            tokenizer,
            chat_template="gemma-3",
        )

        # Optional: prepare the model for inference
        FastLanguageModel.for_inference(model)

        self.model = model
        self.tokenizer = tokenizer

    def translate(self, text):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": f"You are an engine that takes as input the name of a specific location and translates it to the english name of the location. Provide your answer inside brackets. {text}"}
                ]
            }
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,  # Must add for generation
        )

        outputs = self.model.generate(
            **self.tokenizer([text], return_tensors = "pt").to("cuda"),
            max_new_tokens=64,
            temperature=1.0,
            top_p=0.95,
            top_k=64,
        )
        decoded_output = self.tokenizer.batch_decode(outputs)[0]
        s = decoded_output[decoded_output.find("[") + 1:decoded_output.find("]")]
        return s