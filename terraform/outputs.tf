output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_name" {
  description = "Kubernetes cluster name"
  value       = aws_eks_cluster.main.name
}

output "kubeconfig" {
  description = "Kubeconfig for cluster access"
  value       = aws_eks_cluster.main.kubeconfig
  sensitive   = true
}