# Demo Bot - Funcionalidades v1.0

## Visão Geral

Dashboard de visualização de dados de mercado financeiro em tempo real, utilizando a API Twelve Data como fonte de dados e Lightweight Charts para renderização dos gráficos de candlesticks.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐   │
│  │  index.html   │    │  styles.css   │    │ Lightweight   │   │
│  │  (Dashboard)  │    │  (Estilos)    │    │   Charts      │   │
│  └───────────────┘    └───────────────┘    └───────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP Requests
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    FastAPI (routes.py)                     │ │
│  │  GET /              → Serve frontend                       │ │
│  │  GET /api/candles   → Retorna dados OHLCV                  │ │
│  │  GET /api/timeframes → Lista timeframes disponíveis        │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              TwelveDataClient (Data Provider)              │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTPS
┌─────────────────────────────────────────────────────────────────┐
│                    TWELVE DATA API                              │
│                 https://api.twelvedata.com                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Endpoints da API

### `GET /`
Serve a página principal do frontend.

**Resposta:** HTML (`static/index.html`)

---

### `GET /api/candles`
Busca dados OHLCV (Open, High, Low, Close, Volume) de um ativo.

**Parâmetros:**

| Parâmetro | Tipo | Obrigatório | Default | Descrição |
|-----------|------|-------------|---------|-----------|
| `symbol` | string | ✅ | - | Símbolo do ativo (ex: `BTC/USD`, `AAPL`, `DIA`) |
| `timeframe` | string | ❌ | `1min` | Intervalo das candles |
| `count` | int | ❌ | `5000` | Quantidade de candles |

**Timeframes válidos:**
- `1min`, `5min`, `15min`, `30min`, `45min`
- `1h`, `2h`, `4h`, `8h`
- `1day`, `1week`, `1month`

**Exemplo de requisição:**
```
GET /api/candles?symbol=BTC/USD&timeframe=1h&count=100
```

**Resposta (JSON):**
```json
[
  {
    "time": 1703433600,
    "open": 43250.50,
    "high": 43500.00,
    "low": 43100.00,
    "close": 43350.75,
    "volume": 0
  },
  ...
]
```

**Códigos de resposta:**
- `200` - Sucesso
- `400` - Timeframe inválido
- `502` - Erro no provedor de dados (Twelve Data)

---

### `GET /api/timeframes`
Retorna lista de timeframes disponíveis.

**Resposta:**
```json
[
  {"value": "1min", "label": "1min"},
  {"value": "5min", "label": "5min"},
  ...
]
```

---

### `GET /static/{path}`
Serve arquivos estáticos (CSS, JS, imagens).

---

## Frontend

### Biblioteca de Gráficos

**Lightweight Charts v4.1.0** (by TradingView)
- CDN: `https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js`
- Documentação: https://tradingview.github.io/lightweight-charts/

### Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `static/index.html` | Dashboard principal com lógica JavaScript |
| `static/styles.css` | Estilos CSS (tema escuro estilo GitHub) |

### Componentes do Dashboard

#### Header
- **Logo** - Ícone e nome "Demo Bot"
- **Seletor de Símbolo** - Dropdown com ativos disponíveis
- **Seletor de Timeframe** - Dropdown com intervalos de tempo
- **Input de Candles** - Quantidade de candles a buscar
- **Botão Atualizar** - Força atualização manual
- **Botão Auto** - Liga/desliga atualização automática
- **Display de Preço** - Preço atual e variação %
- **Status** - Indicador de conexão

#### Chart Container
- **Gráfico de Candlesticks** - Série principal OHLC
- **Série de Volume** - Histograma (apenas para ativos com volume)
- **Loading Overlay** - Spinner durante carregamento

#### Footer
- **Info OHLCV** - Valores do candle sob o cursor
- **Última Atualização** - Timestamp da última requisição

### Interações Frontend → Backend

```javascript
// Busca candles ao carregar e quando usuário muda parâmetros
async function fetchCandles() {
    const url = `/api/candles?symbol=${symbol}&timeframe=${timeframe}&count=${count}`;
    const response = await fetch(url);
    const data = await response.json();
    
    // Atualiza gráfico
    candlestickSeries.setData(data);
    
    // Atualiza volume (apenas se houver dados)
    if (data.some(d => d.volume > 0)) {
        volumeSeries.setData(volumeData);
    }
}
```

### Atualização Automática

O frontend atualiza automaticamente a cada **60 segundos** quando o modo Auto está ativado.

```javascript
updateInterval = setInterval(fetchCandles, 60000);
```

---

## Ativos Disponíveis

### ETFs (Índices)
| Símbolo | Descrição |
|---------|-----------|
| `DIA` | Dow Jones Industrial Average ETF |
| `SPY` | S&P 500 ETF |
| `QQQ` | Nasdaq 100 ETF |

### Criptomoedas
| Símbolo | Descrição |
|---------|-----------|
| `BTC/USD` | Bitcoin |
| `ETH/USD` | Ethereum |

### Ações
| Símbolo | Descrição |
|---------|-----------|
| `AAPL` | Apple Inc. |
| `GOOGL` | Alphabet Inc. |
| `MSFT` | Microsoft Corporation |
| `TSLA` | Tesla Inc. |
| `NVDA` | NVIDIA Corporation |

### Forex
| Símbolo | Descrição |
|---------|-----------|
| `EUR/USD` | Euro / Dólar |
| `GBP/USD` | Libra / Dólar |

### Commodities
| Símbolo | Descrição |
|---------|-----------|
| `XAU/USD` | Ouro |

---

## Configuração

### Variáveis de Ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `TWELVEDATA_API_KEY` | ✅ | Chave da API Twelve Data |
| `TWELVEDATA_BASE_URL` | ❌ | URL base da API (default: `https://api.twelvedata.com`) |
| `APP_ENV` | ❌ | Ambiente (DEV/PROD) |

### Arquivo `.env`
```env
TWELVEDATA_API_KEY=sua_api_key_aqui
TWELVEDATA_BASE_URL=https://api.twelvedata.com
APP_ENV=DEV
```

---

## Docker

### Executar
```bash
docker compose up --build
```

### Acessar
```
http://localhost:8000
```

### Arquivos Docker

**docker-compose.yml:**
- Porta: `8000:8000`
- Volume: `./:/app` (hot-reload)
- Comando: `uvicorn interfaces.api.routes:app --host 0.0.0.0 --port 8000 --reload`

**Dockerfile:**
- Base: `python:3.11-slim`
- Dependências: `requirements.txt`

---

## Estrutura de Pastas

```
demo-bot/
├── application/           # Casos de uso
│   ├── policies/          # Políticas de negócio
│   └── use_cases/         # FetchLatestOHLCV, FetchHistoricalOHLCV
├── domain/                # Domínio (DDD)
│   ├── entities/          # Candle
│   ├── exceptions/        # DataProviderError
│   ├── services/          # MarketDataService
│   └── value_objects/     # Timeframe, Symbol
├── infrastructure/        # Infraestrutura
│   ├── config/            # Settings
│   ├── data_providers/    # TwelveDataClient
│   └── storage/logging/   # Logger
├── interfaces/            # Interfaces
│   ├── api/               # FastAPI routes
│   ├── controllers/       # MarketDataController
│   └── presenters/        # ConsolePresenter
├── static/                # Frontend
│   ├── index.html
│   └── styles.css
├── tests/                 # Testes
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── main.py
```

---

## Dependências

### Backend (requirements.txt)
```
pytest>=8.0.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
```

### Frontend (CDN)
- Lightweight Charts 4.1.0
- Google Fonts (JetBrains Mono, Space Grotesk)

---

## Limites da API Twelve Data (Plano Gratuito)

| Recurso | Limite |
|---------|--------|
| Créditos/dia | 800 |
| Requisições/minuto | 8 |
| WebSocket connections | 1 |

**Nota:** 1 requisição = 1 crédito, independente da quantidade de candles.

