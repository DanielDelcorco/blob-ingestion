# HTTP Trigger - Documentação de Uso

A Azure Function foi refatorada para usar **HTTP Trigger** em vez de Service Bus. Agora você pode disparar o processamento de um arquivo CSV via uma requisição HTTP POST.

## 📋 Mudanças Principais

### Antes (Service Bus Trigger)
- Consumia eventos do Azure Service Bus
- URL do blob vinha no evento

### Agora (HTTP Trigger)
- Aceita requisições HTTP POST
- Tipo de arquivo é passado no request body
- Configurações de blob e schema vêm de `app/config/file_types_config.py`

---

## 🚀 Como Usar

### 1. Chamar a Function Localmente

```bash
# Iniciar o function host (se não estiver rodando)
func start
```

### 2. Enviar Request HTTP

```bash
curl -X POST http://localhost:7071/api/process \
  -H "Content-Type: application/json" \
  -d '{"fileType": "default_group"}'
```

### 3. Response de Sucesso

```json
{
  "status": "success",
  "fileType": "default_group",
  "docsProcessed": 1250,
  "correlationId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Response de Erro

```json
{
  "error": "Tipo de arquivo 'invalid_type' não suportado. Tipos disponíveis: default_group",
  "correlationId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## ⚙️ Configuração de Variáveis de Ambiente

Adicione ao `local.settings.json` ou ao Azure:

```json
{
  "Values": {
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;...",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_BLOB_ACCOUNT_NAME": "sua-storage-account",
    "AZURE_BLOB_SAS_TOKEN": "sv=2021-01-01&sig=...",
    "MONGO_URI": "mongodb://localhost:27017",
    "MONGO_DB_NAME": "slp",
    "MONGO_COLLECTION_NAME": "defaultGroupDocument",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"
  }
}
```

---

## 📝 Adicionando Novos Tipos de Arquivo

Para adicionar um novo tipo de arquivo, edite `app/config/file_types_config.py`:

```python
FILE_TYPES_CONFIG: Dict[str, FileTypeConfig] = {
    "default_group": FileTypeConfig(...),
    
    # Novo tipo
    "my_new_type": FileTypeConfig(
        name="my_new_type",
        blob_container="my-container",
        blob_path="my_file.csv",
        schema=FileSchema(
            name="my_new_type",
            column_mapping={
                "col1": "field1",
                "col2": "field2",
            },
            boolean_cols=["field1"],
        ),
    ),
}
```

Depois chame:

```bash
curl -X POST http://localhost:7071/api/process \
  -H "Content-Type: application/json" \
  -d '{"fileType": "my_new_type"}'
```

---

## 📊 Códigos HTTP de Resposta

| Código | Significado | Exemplo |
|--------|-----------|---------|
| **200** | Sucesso | `{"status": "success", ...}` |
| **400** | Request inválido | `{"error": "Missing 'fileType'"}` |
| **500** | Erro no servidor | `{"error": "Failed to process blob"}` |

---

## 🔍 Debugging

### Ver logs da function

```bash
func start
```

Os logs aparecem no terminal com `correlation_id` para rastrear requisições.

### Ver traces no Jaeger

1. Abra http://localhost:16686
2. Selecione `blob-ingestion-service`
3. Procure pelo `correlation_id`

---

## 🧪 Testes

```bash
pytest tests/unit/functions/test_process_blob_event.py -v
```

Testes cobrem:
- ✅ Fluxo feliz (sucesso)
- ✅ Missing `fileType`
- ✅ Tipo de arquivo inválido
- ✅ Credenciais do Blob não configuradas

---

## 📌 Notas Importantes

1. **SAS Token**: Certifique-se de que o SAS token tem permissão de leitura no container do blob
2. **Correlation ID**: Gerado automaticamente para cada requisição (UUID)
3. **Timezone**: Todas as datas usam UTC para consistência
4. **Observability**: Spans, métricas e logs são exportados automaticamente para OTEL
