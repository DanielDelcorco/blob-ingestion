# Blob Ingestion - Azure Functions + MongoDB + OpenTelemetry

Este projeto implementa uma Azure Function que:
✅ Lê mensagem do Service Bus contendo a URL de um Blob CSV  
✅ Processa o arquivo em chunks com Pandas  
✅ Insere/upserta no MongoDB em paralelo  
✅ Exporta métricas e tracing com OpenTelemetry  

## Estrutura
- app/core: modelos e regras de negócio
- app/infra: leitura do blob e escrita no Mongo
- functions: Azure Function
- tests: testes unitários com pytest

## Rodando local
