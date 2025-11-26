cat > README.md << 'EOF'
# 📦 Blob Ingestion Service  
**Azure Functions + MongoDB + Pandas + OpenTelemetry + Observability Stack**

Este projeto implementa um pipeline completo de ingestão de arquivos CSV armazenados no Azure Blob Storage, orquestrado via Service Bus, processado por Azure Functions e persistido no MongoDB — com Observability completa via OpenTelemetry.

---

## ✅ 1. Principais Funcionalidades

✔️ Consome eventos do **Azure Service Bus**  
✔️ Baixa e processa CSV em **chunks** usando **Pandas**  
✔️ Realiza **upsert paralelo** no MongoDB  
✔️ Normaliza, mapeia e converte valores booleanos  
✔️ Observability end-to-end:
- Tracing (spans)
- Métricas customizadas
- Logs padronizados  
✔️ Exporta Telemetria para:
- ✅ Jaeger
- ✅ Prometheus
- ✅ Grafana
- ✅ Dynatrace (opcional)  
✔️ Projeto modular, desacoplado e totalmente testável

---

## ✅ 2. Arquitetura Geral

\`\`\`
Service Bus Event
        ↓
Azure Function (trigger)
        ↓
 BlobCsvReader (Infra)
        ↓
 IngestionService (Core)
        ↓
 MongoWriter (Infra)
        ↓
   MongoDB
\`\`\`

### 📐 Camadas

| Camada | Função |
|--------|--------|
| **Core** | Regras de negócio / Orquestração |
| **Infra** | Implementações (Blob, MongoDB) |
| **Config** | Logging + OpenTelemetry |
| **Functions** | Entry point Azure |
| **Tests** | Testes unitários |

---

## ✅ 3. Estrutura de Pastas

\`\`\`
blob-ingestion/
├── app/
│   ├── config/          # logging + otel
│   ├── core/            # domínio e regras
│   ├── infra/           # Mongo + Blob
│   └── utils/           # apoio
├── functions/
│   └── process_blob_event/
├── tests/
├── docker-compose.yml
├── otel-config.yaml
├── prometheus.yml
└── requirements.txt
\`\`\`

---

## ✅ 4. Pré-Requisitos

- Python 3.10+
- Docker e Docker Compose
- Azure Functions Core Tools (local)
- MongoDB local ou remoto

---

## ✅ 5. Setup Local

### 🔹 1. Criar ambiente

\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
\`\`\`

### 🔹 2. Definir variáveis

\`\`\`bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export MONGO_URI=mongodb://localhost:27017
export MONGO_DB_NAME=slp
export MONGO_COLLECTION_NAME=defaultGroupDocument
\`\`\`

---

## ✅ 6. Observability Stack (Jaeger + Prometheus + Grafana)

### 🔹 Subir tudo com 1 comando

\`\`\`bash
docker compose up -d
\`\`\`

### 🔹 Acessar ferramentas

| Ferramenta | URL |
|-----------|-----|
| Jaeger (Tracing) | http://localhost:16686 |
| Prometheus (Metrics) | http://localhost:9090 |
| Grafana (Dashboards) | http://localhost:3000 |

Login Grafana:

\`\`\`
user: admin
pass: admin
\`\`\`

### 🔹 Configurar Grafana

- Data Source → Prometheus
- URL: `http://prometheus:9090`

---

## ✅ 7. Visualizando os Traces

1. Abrir http://localhost:16686  
2. Selecionar o serviço:

\`\`\`
blob-ingestion-service
\`\`\`

3. Clicar **Find Traces**

Você verá spans como:

- `process_blob_event`
- `ingestion_service`
- `blob_download_and_parse`
- `parse_csv_buffer`
- `mongo_bulk_upsert`

---

## ✅ 8. Métricas Disponíveis

| Métrica | Descrição |
|--------|-----------|
| `docs_ingested_total` | Total de documentos processados |
| `chunks_processed_total` | Total de chunks |
| `mongo_docs_upserted_total` | Total upsertado |
| `mongo_upsert_errors_total` | Erros no Mongo |
| `process_memory_mb` | Memória consumida |

---

## ✅ 9. Integração com Dynatrace (Opcional)

### ✅ Sem OneAgent (via OTLP)

\`\`\`bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://<ENV>.live.dynatrace.com/api/v2/otlp"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token <YOUR-TOKEN>"
\`\`\`

### ✅ Via OneAgent

- Zero configuração adicional  
- Tracing automático  
- Detecta dependências automaticamente  

---

## ✅ 10. Executar a Function Localmente

\`\`\`bash
func start
\`\`\`

---

## ✅ 11. Testes

\`\`\`bash
pytest
\`\`\`

Resultado esperado:

✅ 100% verde

---

## ✅ 12. Troubleshooting

### ❌ `"UNAVAILABLE"` OTEL Export
Sem collector rodando.  
✅ Rode:

\`\`\`bash
docker compose up -d
\`\`\`

### ❌ Deprecation `utcnow()`
Corrigido usando `datetime.now(UTC)`.

### ❌ MongoWriter AttributeError
Versão corrigida já inclusa com métricas lazy.

---

## ✅ 13. Roadmap

- Retry com backoff no Mongo  
- Dead Letter Queue  
- Multi-schema CSV registry  
- Dashboard Grafana pré-configurado  
- CI/CD com GitHub Actions  

---

## ✅ 14. Licença

Uso interno / educacional — adaptar conforme necessidade.

---

## ✅ 15. Contato

Para dúvidas, melhorias ou evolução do pipeline, só chamar! 🚀