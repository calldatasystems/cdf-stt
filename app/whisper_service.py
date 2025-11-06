"""
WhisperX STT Service Wrapper with Diarization
Provides thread-safe interface to WhisperX model with speaker diarization
"""

import logging
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
import torch
import whisperx
from pyannote.audio import Pipeline

logger = logging.getLogger(__name__)


class WhisperSTTService:
    """Thread-safe WhisperX service wrapper with diarization support"""

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        download_root: Optional[str] = None
    ):
        """
        Initialize WhisperX model with diarization support

        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to run on (cuda, cpu)
            compute_type: Compute type (float16, int8_float16, int8)
            download_root: Where to cache models
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        # Get HuggingFace token for diarization model
        self.hf_token = os.getenv("HF_TOKEN")
        if not self.hf_token:
            logger.warning("HF_TOKEN not set. Diarization will be disabled. Get token from https://huggingface.co/settings/tokens")

        logger.info(f"Loading WhisperX model: {model_size} on {device}")

        try:
            self.model = whisperx.load_model(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=download_root
            )
            logger.info("WhisperX model loaded successfully")

            # Diarization model will be loaded on-demand
            self.diarization_model = None

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
        word_timestamps: bool = False,
        enable_diarization: bool = False,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio file with optional speaker diarization

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'es'). None for auto-detect
            task: 'transcribe' or 'translate' (to English)
            beam_size: Beam size for decoding
            vad_filter: Use voice activity detection to filter silence
            word_timestamps: Include word-level timestamps
            enable_diarization: Enable speaker diarization
            min_speakers: Minimum number of speakers (for diarization)
            max_speakers: Maximum number of speakers (for diarization)

        Returns:
            Dict with transcription results and speaker labels if diarization enabled
        """
        try:
            logger.info(f"Transcribing: {audio_path} (diarization={enable_diarization})")

            # Load audio
            audio = whisperx.load_audio(audio_path)

            # Step 1: Transcribe with Whisper
            result = self.model.transcribe(
                audio,
                language=language,
                batch_size=16  # WhisperX uses batch processing
            )

            detected_language = result["language"]
            logger.info(f"Detected language: {detected_language}")

            # Step 2: Align whisper output (get word-level timestamps)
            logger.info("Aligning transcription for word-level timestamps...")
            model_a, metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=self.device
            )
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )

            # Step 3: Diarization (if enabled and HF token available)
            speakers_info = None
            if enable_diarization and self.hf_token:
                logger.info("Performing speaker diarization...")
                try:
                    # Load diarization model (lazy loading)
                    if self.diarization_model is None:
                        self.diarization_model = Pipeline.from_pretrained(
                            "pyannote/speaker-diarization-3.1",
                            use_auth_token=self.hf_token
                        )
                        self.diarization_model.to(torch.device(self.device))

                    # Perform diarization
                    diarize_kwargs = {}
                    if min_speakers is not None:
                        diarize_kwargs["min_speakers"] = min_speakers
                    if max_speakers is not None:
                        diarize_kwargs["max_speakers"] = max_speakers

                    diarize_segments = self.diarization_model(audio_path, **diarize_kwargs)

                    # Assign speakers to words
                    result = whisperx.assign_word_speakers(diarize_segments, result)
                    speakers_info = {
                        "enabled": True,
                        "num_speakers": len(set([s['speaker'] for s in result.get("segments", []) if 'speaker' in s]))
                    }
                    logger.info(f"Diarization complete. Detected {speakers_info['num_speakers']} speakers")

                except Exception as e:
                    logger.error(f"Diarization failed: {e}")
                    speakers_info = {"enabled": False, "error": str(e)}
            elif enable_diarization and not self.hf_token:
                speakers_info = {"enabled": False, "error": "HF_TOKEN not set"}
                logger.warning("Diarization requested but HF_TOKEN not available")

            # Format output
            segments_list = []
            full_text = []

            for segment in result["segments"]:
                segment_data = {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip()
                }

                # Add speaker info if available
                if "speaker" in segment:
                    segment_data["speaker"] = segment["speaker"]

                # Add word-level data
                if "words" in segment:
                    segment_data["words"] = [
                        {
                            "word": word["word"],
                            "start": word["start"],
                            "end": word["end"],
                            "score": word.get("score", 1.0),
                            "speaker": word.get("speaker")
                        }
                        for word in segment["words"]
                    ]

                segments_list.append(segment_data)
                full_text.append(segment["text"].strip())

            # Calculate duration from segments
            duration = max([s["end"] for s in segments_list]) if segments_list else 0.0

            response = {
                "text": " ".join(full_text),
                "segments": segments_list,
                "language": detected_language,
                "language_probability": 1.0,  # WhisperX doesn't provide this
                "duration": duration,
                "model": self.model_size,
                "word_timestamps": True  # WhisperX always provides word timestamps after alignment
            }

            if speakers_info:
                response["diarization"] = speakers_info

            logger.info(f"Transcription complete. Language: {detected_language}, Duration: {duration:.2f}s")
            return response

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
