{{/*
Helpers for the 007-wedge chart.
*/}}

{{- define "007-wedge.name" -}}
007-wedge
{{- end }}

{{- define "007-wedge.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "007-wedge.labels" -}}
app.kubernetes.io/name: {{ include "007-wedge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
project: 007
product: wedge
{{- end }}

{{- define "007-wedge.selectorLabels" -}}
app.kubernetes.io/name: {{ include "007-wedge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "007-wedge.serviceAccountName" -}}
{{ include "007-wedge.fullname" . }}-sa
{{- end }}
