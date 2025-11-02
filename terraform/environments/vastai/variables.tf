# Terraform Variables for Vast.ai Deployment

variable "docker_image" {
  description = "Docker image to deploy"
  type        = string
  default     = "ghcr.io/yourusername/cdf-stt:latest"
}

variable "gpu_name" {
  description = "GPU type to use"
  type        = string
  default     = "RTX 4090"
}

variable "num_gpus" {
  description = "Number of GPUs required"
  type        = number
  default     = 1
}

variable "disk_space" {
  description = "Disk space in GB"
  type        = number
  default     = 50
}

variable "api_port" {
  description = "API port to expose"
  type        = number
  default     = 8000
}

variable "whisper_model_size" {
  description = "Whisper model size"
  type        = string
  default     = "large-v3"
}

variable "whisper_device" {
  description = "Device to run Whisper on"
  type        = string
  default     = "cuda"
}

variable "whisper_compute_type" {
  description = "Compute type for Whisper"
  type        = string
  default     = "float16"
}
