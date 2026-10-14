{{/*
Per-adapter NetworkPolicy (spec §NetworkPolicy Template).
*/}}
{{- define "m11.networkpolicy" -}}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: m11-{{ .vendor }}
  namespace: {{ .firm }}-m11-{{ .vendor }}
spec:
  podSelector:
    matchLabels:
      app: m11-{{ .vendor }}
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              firm: {{ .firm }}
          podSelector:
            matchLabels:
              app: m6-mcp-gateway
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
{{- range .egressFQDNs }}
    - toFQDNs:
        - matchName: {{ . | quote }}
      ports:
        - protocol: TCP
          port: 443
{{- end }}
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: {{ .secretsNamespace }}
      ports:
        - protocol: TCP
          port: 443
{{- end -}}
