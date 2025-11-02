# CDF STT - Vast.ai Deployment
# Uses Vast.ai RTX 4090 GPU instance

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    vastai = {
      source  = "aalekhpatel07/vastai"
      version = "~> 0.1.0"
    }
  }
}

# Configure Vast.ai provider
# Requires VASTAI_API_KEY environment variable
provider "vastai" {
  # API key from environment: export VASTAI_API_KEY=your_key
}

locals {
  project_name = "cdf-stt"
  environment  = "prod"

  # RTX 4090 requirements
  gpu_name = "RTX 4090"
  gpu_ram  = 24  # GB
  num_gpus = 1

  # Image and port configuration
  docker_image = "ghcr.io/yourusername/cdf-stt:latest"  # TODO: Update with your registry
  api_port     = 8000

  tags = {
    Project     = "CDF STT"
    Environment = "prod"
    ManagedBy   = "Terraform"
    Repository  = "cdf-stt"
  }
}

# Search for available RTX 4090 instances
# Note: This is a data source to find suitable instances
# You'll need to manually select an instance ID or use the Vast.ai CLI/API
resource "vastai_instance" "stt" {
  # Instance configuration
  image = local.docker_image

  # GPU requirements - targeting RTX 4090
  # These filters help find suitable instances
  gpu_name = local.gpu_name
  num_gpus = local.num_gpus

  # Minimum requirements
  disk_space = 50  # GB

  # Port mapping
  port_mappings = {
    "${local.api_port}" = local.api_port
  }

  # Environment variables
  env = {
    WHISPER_MODEL_SIZE  = "large-v3"
    WHISPER_DEVICE      = "cuda"
    WHISPER_COMPUTE_TYPE = "float16"
  }

  # SSH public key for access (optional)
  # ssh_key = file("~/.ssh/id_rsa.pub")

  # Auto-restart on failure
  on_failure = "restart"
}
