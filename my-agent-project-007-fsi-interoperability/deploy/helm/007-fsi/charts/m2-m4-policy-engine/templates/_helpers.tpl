{{/*
Shared helpers for Project 007 trust-layer sub-charts.
*/}}

{{/* Fully qualified app name (release + chart). */}}
{{- define "007.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Chart name (for labels). */}}
{{- define "007.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{/* Common labels applied to every resource. */}}
{{- define "007.labels" -}}
app.kubernetes.io/name: {{ include "007.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/component: trust-layer
app.kubernetes.io/part-of: 007-fsi
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/* Selector labels (stable -- excludes chart version). */}}
{{- define "007.selectorLabels" -}}
app.kubernetes.io/name: {{ include "007.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Compute imagePullPolicy.
* Explicit `image.pullPolicy` takes precedence.
* Else `:latest` -> Always (dev tags).
* Else pinned tag (vX.Y.Z, @sha256:, sha256:) -> IfNotPresent.
*/}}
{{- define "007.imagePullPolicy" -}}
{{- if .Values.image.pullPolicy -}}
{{ .Values.image.pullPolicy }}
{{- else if eq .Values.image.tag "latest" -}}
Always
{{- else if hasPrefix "sha256:" .Values.image.tag -}}
IfNotPresent
{{- else if hasPrefix "@sha256:" .Values.image.tag -}}
IfNotPresent
{{- else if regexMatch "^v\\d" .Values.image.tag -}}
IfNotPresent
{{- else -}}
Always
{{- end -}}
{{- end -}}

{{/*
Full image reference, honouring the umbrella's global.imageRegistry.
*/}}
{{- define "007.image" -}}
{{- $registry := "" -}}
{{- if and .Values.global .Values.global.imageRegistry -}}
{{- $registry = printf "%s/" .Values.global.imageRegistry -}}
{{- end -}}
{{- printf "%s%s:%s" $registry .Values.image.repository .Values.image.tag -}}
{{- end -}}

{{/*
ServiceAccount name for IRSA / per-tenant KMS.
*/}}
{{- define "007.serviceAccountName" -}}
{{- include "007.fullname" . -}}
{{- end -}}
