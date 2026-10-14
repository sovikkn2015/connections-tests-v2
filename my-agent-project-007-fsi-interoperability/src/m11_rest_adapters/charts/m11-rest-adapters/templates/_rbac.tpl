{{/* Default (read-only) Role for SFDC / Orion / eMoney. */}}
{{- define "m11.rbac.default" -}}
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: m11-{{ .vendor }}-secret-read
  namespace: {{ .firm }}-m11-{{ .vendor }}
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["m11-{{ .vendor }}-mtls-certs"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: m11-{{ .vendor }}-secret-read
  namespace: {{ .firm }}-m11-{{ .vendor }}
subjects:
  - kind: ServiceAccount
    name: m11-{{ .vendor }}
    namespace: {{ .firm }}-m11-{{ .vendor }}
roleRef:
  kind: Role
  name: m11-{{ .vendor }}-secret-read
  apiGroup: rbac.authorization.k8s.io
{{- end -}}

{{/* Schwab ADDITIONAL narrow-write — §RBAC Template. */}}
{{- define "m11.rbac.schwab.rt" -}}
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: m11-schwab-refresh-token-rotate
  namespace: {{ .firm }}-m11-schwab
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["m11-schwab-refresh-token"]
    verbs: ["get", "update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: m11-schwab-refresh-token-rotate
  namespace: {{ .firm }}-m11-schwab
subjects:
  - kind: ServiceAccount
    name: m11-schwab
    namespace: {{ .firm }}-m11-schwab
roleRef:
  kind: Role
  name: m11-schwab-refresh-token-rotate
  apiGroup: rbac.authorization.k8s.io
{{- end -}}
