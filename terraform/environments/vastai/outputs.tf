# Terraform Outputs for Vast.ai Deployment

output "instance_id" {
  description = "Vast.ai instance ID"
  value       = vastai_instance.stt.id
}

output "instance_status" {
  description = "Instance status"
  value       = vastai_instance.stt.status
}

output "public_ip" {
  description = "Public IP address of the instance"
  value       = vastai_instance.stt.public_ipaddr
}

output "ssh_host" {
  description = "SSH host"
  value       = vastai_instance.stt.ssh_host
}

output "ssh_port" {
  description = "SSH port"
  value       = vastai_instance.stt.ssh_port
}

output "api_url" {
  description = "STT API URL"
  value       = "http://${vastai_instance.stt.public_ipaddr}:${local.api_port}"
}

output "connection_info" {
  description = "Connection information"
  value = {
    api_url    = "http://${vastai_instance.stt.public_ipaddr}:${local.api_port}"
    health_url = "http://${vastai_instance.stt.public_ipaddr}:${local.api_port}/health"
    docs_url   = "http://${vastai_instance.stt.public_ipaddr}:${local.api_port}/docs"
    ssh        = "ssh -p ${vastai_instance.stt.ssh_port} root@${vastai_instance.stt.ssh_host}"
  }
}
