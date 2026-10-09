"""Cloud-only entry point for the free Hugging Face ZeroGPU Space."""

import os
import logging
import json

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ["GRADIO_RUN_HISTORY"] = "false"

# Import spaces before torch so ZeroGPU's CUDA emulation is active at startup.
import spaces
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from starlette.middleware import Middleware
from lmformatenforcer import CharacterLevelParserConfig, JsonSchemaParser

from app.free_space import build_ui, NoStoreMiddleware
from app.constrained_tokens import build_tokenizer_data, prefix_function

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=False)
# Build the CPU tokenizer trie once, outside the metered GPU function.
tokenizer_data = build_tokenizer_data(tokenizer)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, revision=MODEL_REVISION, trust_remote_code=False,
    dtype=torch.bfloat16, device_map="cuda", use_safetensors=True,
).eval()


@spaces.GPU(duration=45)
def generate(messages):
    request = json.loads(messages[1]["content"])
    ids = [source["id"] for source in request["evidence"]]
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 320},
            "citations": {"type": "array", "items": {"type": "string", "enum": ids}, "minItems": 1, "maxItems": len(ids)},
        },
        "required": ["summary", "citations"],
        "additionalProperties": False,
    }
    config = CharacterLevelParserConfig()
    config.alphabet += ''.join(chr(c) for c in range(0x0900, 0x0980))
    config.force_json_field_order = True
    prefix = prefix_function(tokenizer_data, JsonSchemaParser(schema, config=config))
    inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=1536, do_sample=False, pad_token_id=tokenizer.eos_token_id, prefix_allowed_tokens_fn=prefix)
    return {
        "text": tokenizer.decode(output[0, inputs["input_ids"].shape[-1]:], skip_special_tokens=True),
        "tokens": output.shape[-1] - inputs["input_ids"].shape[-1],
    }


def cloud_summary(messages):
    result = generate(messages)
    # Count only: never log questions, sources, or generated explanations.
    logging.getLogger(__name__).warning("Model generated %s tokens (limit 1536)", result["tokens"])
    return result["text"]


demo, css = build_ui(cloud_summary)

if __name__ == "__main__":
    demo.queue(max_size=20).launch(
        server_name="0.0.0.0", server_port=7860, css=css, ssr_mode=False,
        show_error=False, run_history=False,
        app_kwargs={"middleware": [Middleware(NoStoreMiddleware)]},
    )
