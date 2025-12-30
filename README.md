# Demo Bot (Backend)

Backend para coleta e análise de dados de mercado seguindo rigorosamente Clean Architecture + DDD. A aplicação consome a API Twelve Data, aplica políticas de timeframe, detecta tendências e identifica zonas de acumulação (liquidez) totalmente configuráveis.

---

## Visão Geral de Arquitetura

```
Entrada Externa (CLI / HTTP) ──► Controllers ──► DTO/Validação ──► Use Cases
                                              │                   │
                                              ▼                   ▼
                                          Domain Entities   Domain Services
                                              │                   │
                                              ▼                   ▼
                                         Repository Interfaces ─► Repository Impl.
```

- **Domain (`domain/`)**: entidades, value objects e serviços puros (sem dependências externas). Exemplos: `Candle`, `TrendDetector`, `LiquidityIndicator` e configurações de acumulação.
- **Application (`application/`)**: use cases e políticas que orquestram as regras de negócio. Ex.: `FetchLatestOHLCV`, `GenerateTradingDecision`, `DetectLiquidityZones`.
- **Interfaces (`interfaces/`)**: controllers e modelos expostos ao mundo externo (FastAPI, CLI). Ex.: `MarketDataController`, `TradingController`, `LiquidityController`, modelos Pydantic em `interfaces/api/models.py`.
- **Infrastructure (`infrastructure/`)**: integração com provedores e configuração. Ex.: `TwelveDataClient`, carregadores de configuração, logging.
- **Composition Root (`main.py` e `interfaces/api/routes.py`)**: ponto de montagem das dependências, sem lógica de domínio.
- **Reuso de dados**: `CandleCache` (`infrastructure/storage/cache/candle_cache.py`) persiste candles em JSON para que endpoints diferentes reutilizem a mesma coleta sem refazer chamadas externas.

---

## Fluxos Importantes

### Consulta de dados de mercado
1. **Controller**: `MarketDataController` recebe símbolo, timeframe e contagem.
2. **Use Case**: `FetchLatestOHLCV` valida o timeframe com `TimeframePolicy` e chama o serviço de mercado.
3. **Domain Service**: `TwelveDataClient` (implementa `MarketDataService`) consulta o provedor externo e retorna `Candle`.

### Geração de decisões de trade
1. **Controller**: `TradingController` orquestra a chamada ao use case.
2. **Use Case**: `GenerateTradingDecision` coleta candles, roda `TrendDetector` e aplica regras de momentum.
3. **Resultado**: retorna `TradingDecision` com timestamp, preço e racional.

### Detecção de acumulação/liquidez
1. **Configuração**: `LiquidityIndicatorSettings` (arquivo dedicado em `domain/indicators/liquidity/settings.py`) define parâmetros como range máximo e toques mínimos.
2. **Use Case**: `DetectLiquidityZones` instancia `LiquidityIndicator` com as configurações carregadas e garante que os candles estejam em ordem cronológica.
3. **Domain Indicator**: `LiquidityIndicator` analisa as janelas, calcula força, merge de zonas e entrega `LiquiditySignal` com zonas de acumulação.
4. **Controller/API**: `LiquidityController` expõe o resultado para os endpoints `/api/indicators/liquidity` e `/api/analysis`.

---

## Configuração

### Variáveis de ambiente gerais
- `APP_ENV`: `DEV` | `PAPER` | `PROD` (default `DEV`).
- `TWELVEDATA_API_KEY`: **obrigatório** para chamadas ao provedor.
- `TWELVEDATA_BASE_URL`: opcional para apontar para outro endpoint Twelve Data.
- `LOG_LEVEL`: nível de log numérico ou nome (`INFO`, `DEBUG`, etc.).

### Parâmetros de acumulação (carregados por `infrastructure/config/liquidity.py`)
| Variável | Default | Descrição |
| --- | --- | --- |
| `ACCUMULATION_MIN_CANDLES` | `25` | Mínimo de candles por zona. |
| `ACCUMULATION_MAX_RANGE_PERCENT` | `0.8` | Range máximo (%) vs preço médio para considerar consolidação. |
| `ACCUMULATION_MIN_STRENGTH` | `0.55` | Força mínima (0-1) para reportar zona. |
| `ACCUMULATION_MIN_BOUNDARY_TOUCHES` | `3` | Toques mínimos em suporte/resistência para confirmar zona. |
| `ACCUMULATION_MAX_ZONES` | `5` | Limite de zonas retornadas. |
| `ACCUMULATION_MIN_GAP_BETWEEN_ZONES` | `15` | Gap mínimo (em candles) entre zonas para evitar clusters. |
| `ACCUMULATION_SEED_CANDLES` | `50` | Janela inicial para validar uma acumulação antes de estender o range. |
| `ACCUMULATION_BREAK_INVALID_PCT` | `0.2` | Penetração percentual do range que invalida a acumulação (range break). |
| `ACCUMULATION_BREAK_CONFIRM_CANDLES` | `2` | Closes consecutivos fora do range necessários para confirmar o break. |
| `ACCUMULATION_SWEEP_TOLERANCE_PCT` | `0.05` | Penetração máxima tolerada (em % do range) para tratar o furo como sweep e manter a acumulação. |

Todas as validações de limite são aplicadas no carregador de configuração e no próprio value object `LiquidityIndicatorSettings`.

---

## Como Executar

### Dependências
- Python 3.11+
- Instale as libs:
  ```bash
  pip install -r requirements.txt
  ```

### CLI (via `main.py`)
```bash
export TWELVEDATA_API_KEY="sua-api-key"
python main.py --symbol AAPL --timeframe 1min --count 5           # candles recentes
python main.py --symbol AAPL --timeframe 15min --historical \
  --start 2024-01-01T00:00:00 --end 2024-01-02T00:00:00 --limit 100
```

### API (FastAPI)
- A app é criada em `interfaces/api/routes.py` (função `create_app`).
- Exemplos de endpoints principais:
  - `GET /api/candles`: retorna OHLCV para gráfico (ordenado do mais antigo para o mais recente).
  - `GET /api/market-data`: une candles + decisões do bot numa única chamada.
  - `GET /api/indicators/trend`: retorna swings, BOS e direção de tendência.
  - `GET /api/indicators/liquidity`: retorna zonas de acumulação configuráveis.
  - `GET /api/analysis`: entrega candles, tendência e liquidez em um único payload.

---

## Mapa de Código
- `domain/entities/candle.py`: entidade de candle (OHLCV).
- `domain/services/trend_detector.py`: detecção de tendência (swings e BOS).
- `domain/indicators/liquidity/`: indicador de acumulação e value objects (`models.py`), configurações (`settings.py`).
- `application/use_cases/`: casos de uso para fetch de mercado, decisões de trade e detecção de liquidez.
- `interfaces/controllers/`: controllers por responsabilidade (`market_data`, `trading`, `liquidity`).
- `interfaces/api/models.py`: DTOs de entrada/saída da API FastAPI.
- `infrastructure/data_providers/twelve_data_client.py`: integração com Twelve Data (implementa `MarketDataService`).
- `infrastructure/config/`: carregamento de variáveis de ambiente (`settings.py`) e parâmetros de acumulação (`liquidity.py`).
- `main.py`: orquestração para execução CLI.

---

## Testes
Execute a suíte de testes com:
```bash
pytest
```

---

## Docker
Construção e execução:
```bash
docker build -t demo-bot .
docker run --rm \
  -e TWELVEDATA_API_KEY="sua-api-key" \
  -e APP_ENV=PROD \
  demo-bot \
  --symbol AAPL --timeframe 1min --count 5
```

---

## Notas de Segurança e Boas Práticas
- Nunca armazene chaves de API em código; use variáveis de ambiente.
- Todas as entradas externas são validadas em controllers/DTOs antes de chegar ao domínio.
- O domínio permanece livre de dependências externas (rede, banco, frameworks).
- Configurações de acumulação são centralizadas e validadas no arquivo dedicado para evitar strings mágicas e hardcode.
