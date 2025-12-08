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
# Blob Ingestion Service

Azure Functions + MongoDB + Pandas + OpenTelemetry — pipeline para ingestão
de CSVs armazenados em Azure Blob Storage e escrita por upsert no MongoDB.

Principais pontos:
- Entrada HTTP trigger (`POST /api/process`) que seleciona o tipo de arquivo (`fileType`).
- Pipeline configurável por tipo de arquivo (`app/config/file_types_config.py`).
- Streaming CSV em chunks via `BlobCsvReader` + processamento paralelo com `IngestionService`.
- Persistência com upsert no MongoDB via `MongoWriter`.
- Observability: logs, métricas e traces via OpenTelemetry.

**Observação:** o projeto foi refatorado para expor a função como HTTP trigger (request JSON com `fileType`).

## Índice

- [Fluxo de processamento](#fluxo-de-processamento)
- [Recursos disponíveis](#recursos-disponiveis)
- [Rodando localmente](#rodando-localmente)
- [Docker / Container](#docker--container)
- [Testes](#testes)
- [Instrumentação (logs, métricas, traces)](#instrumentacao-logs-metricas-traces)
- [Variáveis de ambiente mínimas](#variaveis-de-ambiente-minimas)

## Fluxo de processamento

1. Cliente envia `POST /api/process` com JSON: `{"fileType":"customer_data", "correlationId":"..."}`.
2. A função valida e chama `get_file_type_config(fileType)`.
3. `BlobClientFactory` constrói um `BlobClient` para o container/path configurado.
4. `BlobCsvReader` faz stream do blob em chunks e normaliza colunas conforme `FileSchema`.
5. `IngestionService` processa chunks em paralelo e chama `MongoWriter.bulk_upsert()` usando `key_fields` do `FileTypeConfig`.
6. Métricas e spans são emitidos via OpenTelemetry; logs estruturados são gravados usando o logger central.

## Recursos disponíveis

- `app/config/file_types_config.py`: registro de tipos de arquivo — blob container, blob path, mapeamento de colunas, `key_fields`, collection.
- `app/config/blob_config.py` / `MongoClientFactory`: fábricas para criar clientes (testáveis, isolam env vars).
- `app/infra/blob/blob_csv_reader.py`: streaming CSV reader (pandas chunks, mapeamento, booleans).
- `app/core/services/ingestion_service.py`: orquestrador (paralelismo, upsert, métricas).
- `functions/process_blob_event/__init__.py`: entrada HTTP da Function.

## Rodando localmente

### 1) Ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Com Azure Functions Core Tools

```bash
func start
```

Endpoint de teste (exemplo):

```http
POST http://localhost:7071/api/process
Content-Type: application/json

{ "fileType": "customer_data", "correlationId": "abc-123" }
```

## Docker / Container

Há um `Dockerfile` preparado para o runtime do Azure Functions.

### Build local

```bash
docker build -t blob-ingestion:local .
```

### Run local (com arquivo de ambiente)

```bash
cp local.settings.env.example local.settings.env
# editar local.settings.env e preencher segredos
docker run --env-file local.settings.env -p 8080:80 blob-ingestion:local
```

### Publicar imagem (exemplo ACR)

```bash
docker tag blob-ingestion:local myacr.azurecr.io/blob-ingestion:v1
docker push myacr.azurecr.io/blob-ingestion:v1
az functionapp create -g <rg> -n <name> --plan <plan> --storage-account <sa> \
       --deployment-container-image-name myacr.azurecr.io/blob-ingestion:v1
```

## Testes

```bash
.venv/bin/python -m pytest tests/unit/ -q
```

## Instrumentação (logs, métricas, traces)

- **Logging:** configurado em `app/config/logging_config.py`. Use `LOG_LEVEL` para controlar verbosidade.
- **Traces e métricas:** configurados em `app/config/otel.py`.
       - `setup_otel(logger)` retorna providers e uma função `shutdown_otel()` idempotente que deve ser chamada ao finalizar a Function.
       - Configure `OTEL_EXPORTER_OTLP_ENDPOINT` para apontar para o collector (ex.: `http://localhost:4317`).

- **Métricas principais**:
       - `docs_ingested_total`
       - `chunks_processed_total`
       - `mongo_docs_upserted_total`
       - `mongo_upsert_errors_total`
       - `process_memory_mb`

- **Traces:** spans criados para `process_blob_event`, `ingestion_service` e operações infra (blob/mongo).

## Variáveis de ambiente mínimas

Preencha `local.settings.env` com as chaves necessárias (existe o `local.settings.env.example` no repositório):

- `AZURE_BLOB_ACCOUNT_NAME`, `AZURE_BLOB_SAS_TOKEN`
- `DEFAULT_GROUP_BLOB_CONTAINER`, `CUSTOMER_BLOB_CONTAINER`
- `MONGO_URI`, `MONGO_DB_NAME`, `DEFAULT_GROUP_MONGO_COLLECTION`, `CUSTOMER_MONGO_COLLECTION`
- `OTEL_EXPORTER_OTLP_ENDPOINT` (opcional)
- `FUNCTIONS_WORKER_RUNTIME=python`
- `AzureWebJobsStorage` (Functions host requirement)

## Notas operacionais

- Se não houver OTLP collector ativo, verá `StatusCode.UNAVAILABLE` nos logs; isto não impede o processamento.
- `get_file_type_config()` valida que `key_fields` configurados existam no `schema.column_mapping`.
- Para evitar mensagens de exportador durante testes, desabilite exportadores ou configure um endpoint válido.

## Contribuição

- Execute os testes antes de abrir PRs. Bugfixes e melhorias em `file_types_config` e factories são bem-vindas.

## Contato

- Abra uma issue ou PR para melhorias ou dúvidas.
