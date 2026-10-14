{{/*
Project 007 FSI Platform — Helm template helpers
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "007-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "007-platform.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels for all resources.
*/}}
{{- define "007-platform.labels" -}}
helm.sh/chart: {{ include "007-platform.name" . }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: 007-fsi-platform
{{- end }}

{{/*
Selector labels for a specific module.
  Usage: {{ include "007-platform.selectorLabels" (dict "module" "m6-mcp-gateway" "context" .) }}
*/}}
{{- define "007-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ .module }}
app.kubernetes.io/instance: {{ .context.Release.Name }}
{{- end }}

{{/*
Module image reference.
  Usage: {{ include "007-platform.image" (dict "image" .Values.m6McpGateway.image "global" .Values.global) }}
*/}}
{{- define "007-platform.image" -}}
{{- if .global.imageRegistry }}
{{- printf "%s/%s:%s" .global.imageRegistry .image.repository .image.tag }}
{{- else }}
{{- printf "%s:%s" .image.repository .image.tag }}
{{- end }}
{{- end }}
