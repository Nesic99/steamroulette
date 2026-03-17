{{/*
Expand the name of the chart.
*/}}
{{- define "steam-roulette.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "steam-roulette.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend image
*/}}
{{- define "steam-roulette.backendImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.repository }}-backend:{{ .Values.backend.image.tag }}
{{- end }}

{{/*
Frontend image
*/}}
{{- define "steam-roulette.frontendImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.repository }}-frontend:{{ .Values.frontend.image.tag }}
{{- end }}
