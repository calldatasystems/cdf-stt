"""
Faster-Whisper STT Service Wrapper
Provides thread-safe interface to Faster-Whisper model
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
import torch
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class WhisperSTTService:
    """Thread-safe Faster-Whisper service wrapper"""

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        download_root: Optional[str] = None
    ):
        """
        Initialize Faster-Whisper model

        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to run on (cuda, cpu)
            compute_type: Compute type (float16, int8_float16, int8)
            download_root: Where to cache models
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        logger.info(f"Loading Faster-Whisper model: {model_size} on {device}")

        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=download_root
            )
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        vad_filter: bool = True,
        word_timestamps: bool = False
    ) -> Dict[str, Any]:
        """
        Transcribe audio file

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'es'). None for auto-detect
            task: 'transcribe' or 'translate' (to English)
            beam_size: Beam size for decoding
            vad_filter: Use voice activity detection to filter silence
            word_timestamps: Include word-level timestamps

        Returns:
            Dict with transcription results
        """
        try:
            logger.info(f"Transcribing: {audio_path}")

            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                task=task,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=word_timestamps
            )

            # Convert generator to list and extract data
            segments_list = []
            full_text = []

            for segment in segments:
                segment_data = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                }

                if word_timestamps and hasattr(segment, 'words'):
                    segment_data["words"] = [
                        {
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        }
                        for word in segment.words
                    ]

                segments_list.append(segment_data)
                full_text.append(segment.text.strip())

            result = {
                "text": " ".join(full_text),
                "segments": segments_list,
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "model": self.model_size
            }

            logger.info(f"Transcription complete. Language: {info.language}, Duration: {info.duration:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        return [
            "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca", "nl",
            "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms", "cs", "ro",
            "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy",
            "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk", "br", "eu",
            "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km",
            "sn", "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", "lo",
            "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl", "mg",
            "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"
        ]

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        }
