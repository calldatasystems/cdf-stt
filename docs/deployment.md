# CDF STT Deployment Guide

## Overview

This guide covers deploying the CDF Speech-to-Text service to Vast.ai GPU instances.

## Prerequisites

1. **Vast.ai Account**
   - Sign up at https://vast.ai/
   - Get your API key from Console > Account > API Keys

2. **GitHub Secrets**
   - `VASTAI_API_KEY`: Your Vast.ai API key
   - `GITHUB_TOKEN`: Automatically provided by GitHub Actions

## Deployment Options

### Option 1: GitHub Actions (Recommended)

The repository includes a GitHub Actions workflow that automatically:
1. Builds the Docker image
2. Pushes to GitHub Container Registry
3. Deploys to Vast.ai RTX 4090 instance

**Setup:**

1. Add Vast.ai API key to GitHub Secrets:
   ```
   Settings > Secrets and variables > Actions > New repository secret
   Name: VASTAI_API_KEY
   Value: <your-api-key>
   ```

2. Push to main branch:
   ```bash
   git push origin main
   ```

3. Monitor deployment:
   ```
   Actions tab > Deploy CDF STT (Vast.ai)
   ```

### Option 2: Manual Deployment via Vast.ai CLI

1. **Install Vast.ai CLI**
   ```bash
   wget https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py
   chmod +x vast.py
   sudo mv vast.py /usr/local/bin/vast
   ```

2. **Configure API Key**
   ```bash
   vast set api-key YOUR_API_KEY
   ```

3. **Search for RTX 4090 Instances**
   ```bash
   vast search offers 'gpu_name=RTX 4090 num_gpus=1 disk_space>=50 reliability>0.95'
   ```

4. **Create Instance**
   ```bash
   vast create instance OFFER_ID \
     --image ghcr.io/USERNAME/cdf-stt:latest \
     --disk 50 \
     --label cdf-stt-prod \
     --env "WHISPER_MODEL_SIZE=large-v3" \
     --env "WHISPER_DEVICE=cuda" \
     --env "WHISPER_COMPUTE_TYPE=float16" \
     --ports 8000:8000
   ```

5. **Get Instance Info**
   ```bash
   vast show instances
   ```

### Option 3: Terraform

1. **Install Terraform Provider**
   ```bash
   cd terraform/environments/vastai
   terraform init
   ```

2. **Set API Key**
   ```bash
   export VASTAI_API_KEY=your_key
   ```

3. **Deploy**
   ```bash
   terraform plan
   terraform apply
   ```

4. **Get Connection Info**
   ```bash
   terraform output
   ```

## Testing the Deployment

1. **Health Check**
   ```bash
   curl http://INSTANCE_IP:8000/health
   ```

2. **Test Transcription**
   ```bash
   curl -X POST http://INSTANCE_IP:8000/transcribe \
     -F "file=@test_audio.wav"
   ```

3. **View API Documentation**
   ```
   http://INSTANCE_IP:8000/docs
   ```

## Cost Monitoring

- RTX 4090 instances on Vast.ai: ~$0.30-0.50/hour
- Monitor usage: `vast show instances`
- Stop instance: `vast destroy instance INSTANCE_ID`

## Troubleshooting

### Instance Not Starting
```bash
# Check instance status
vast show instances

# View instance logs
vast logs INSTANCE_ID
```

### API Not Responding
```bash
# SSH into instance
vast ssh INSTANCE_ID

# Check container logs
docker logs -f $(docker ps -q)
```

### Model Download Issues
The first startup downloads the Whisper model (~3GB). This can take 5-10 minutes.

## Asterisk Integration

To integrate with CDF Asterisk, configure Asterisk to send audio recordings to the STT API:

```bash
# From Asterisk dialplan
curl -X POST http://STT_INSTANCE_IP:8000/transcribe \
  -F "file=@/var/spool/asterisk/recording.wav"
```

See `docs/asterisk-integration.md` for detailed integration guide.
