"""
Qwen3-VL-2B engine (Hugging Face transformers).

torch/transformers are imported lazily so the module (and the MS2 test suite / CI) works
without a GPU or the heavy deps installed.

Residency:
  VLM_KEEP_LOADED=true  -> load() once at startup, stay resident.
  VLM_KEEP_LOADED=false -> load per call and free VRAM afterwards.
"""
import gc
import logging
import threading
import time
from typing import Any, Dict, Optional

from ms2_llm import config

logger = logging.getLogger("ms2_llm.vlm")


class VLMNotAvailable(RuntimeError):
    """Raised when the model cannot be loaded (missing deps, no weights, OOM)."""


class VLMEngine:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or config.VLM_MODEL_PATH
        self.model = None
        self.processor = None
        self.device = "cpu"
        self.load_seconds: Optional[float] = None
        self.last_error: Optional[str] = None
        # Serialises GPU access; infer() runs in a worker thread (see main.py)
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self.model is not None

    # ── lifecycle ────────────────────────────────────────────────────────
    def load(self) -> None:
        if self.loaded:
            return
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as e:
            self.last_error = f"VLM dependencies missing: {e}"
            raise VLMNotAvailable(self.last_error) from e

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = (
            torch.bfloat16 if (self.device == "cuda" and torch.cuda.is_bf16_supported())
            else (torch.float16 if self.device == "cuda" else torch.float32)
        )
        logger.info("Loading Qwen3-VL-2B from %s on %s (%s)...", self.model_path, self.device, dtype)
        t0 = time.time()
        try:
            self.processor = AutoProcessor.from_pretrained(self.model_path)
            self.model = AutoModelForImageTextToText.from_pretrained(
                self.model_path,
                dtype=dtype,
                device_map="auto" if self.device == "cuda" else None,
            )
        except Exception as e:
            self.model = self.processor = None
            self.last_error = f"model load failed: {e}"
            logger.error(self.last_error, exc_info=True)
            raise VLMNotAvailable(self.last_error) from e

        self.load_seconds = round(time.time() - t0, 2)
        self.last_error = None
        logger.info("Qwen3-VL-2B loaded in %.2fs. %s", self.load_seconds, self.memory_stats())

    def unload(self) -> None:
        self.model = None
        self.processor = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        logger.info("Qwen3-VL-2B unloaded.")

    def memory_stats(self) -> Dict[str, Any]:
        try:
            import torch
            if torch.cuda.is_available():
                return {
                    "vram_allocated_mb": round(torch.cuda.memory_allocated() / 2**20, 1),
                    "vram_reserved_mb": round(torch.cuda.memory_reserved() / 2**20, 1),
                    "vram_peak_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1),
                }
        except ImportError:
            pass
        return {}

    def status(self) -> Dict[str, Any]:
        return {
            "status": "ok" if self.loaded else "not_loaded",
            "keep_loaded": config.VLM_KEEP_LOADED,
            "device": self.device,
            "model_path": self.model_path,
            "load_seconds": self.load_seconds,
            "error": self.last_error,
            **self.memory_stats(),
        }

    # ── inference ────────────────────────────────────────────────────────
    def infer(self, system: str, user: str, image: Any = None, max_new_tokens: Optional[int] = None) -> str:
        """Blocking generation. `image` is a PIL.Image or None (text-only)."""
        with self._lock:
            transient = not self.loaded
            if transient:
                self.load()
            try:
                return self._generate(system, user, image, max_new_tokens or config.VLM_MAX_NEW_TOKENS)
            finally:
                if transient and not config.VLM_KEEP_LOADED:
                    self.unload()

    def _generate(self, system: str, user: str, image: Any, max_new_tokens: int) -> str:
        import torch
        from qwen_vl_utils import process_vision_info

        user_content = []
        if image is not None:
            user_content.append({"type": "image", "image": image, "max_pixels": config.VLM_MAX_PIXELS})
        user_content.append({"type": "text", "text": user})
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        text_prompt = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text_prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(self.model.device)

        with torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,  # deterministic JSON
                temperature=None,
                top_p=None,
                top_k=None,
            )
        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
        return self.processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()


# Global instance (model is loaded in the FastAPI lifespan, not at import)
engine = VLMEngine()
