{{/*
Helpers for the M13 FIX Bridge sub-chart.
*/}}

{{- define "007.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "007.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "007.labels" -}}
app.kubernetes.io/name: {{ include "007.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/component: m13-fix-bridge
app.kubernetes.io/part-of: 007-fsi
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{- define "007.selectorLabels" -}}
app.kubernetes.io/name: {{ include "007.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

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

{{- define "007.image" -}}
{{- $registry := "" -}}
{{- if and .Values.global .Values.global.imageRegistry -}}
{{- $registry = printf "%s/" .Values.global.imageRegistry -}}
{{- end -}}
{{- printf "%s%s:%s" $registry .Values.image.repository .Values.image.tag -}}
{{- end -}}

{{- define "007.serviceAccountName" -}}
{{- include "007.fullname" . -}}
{{- end -}}

{{- define "007.headlessServiceName" -}}
{{- printf "%s-headless" (include "007.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
