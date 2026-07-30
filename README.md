# Projeto Final — Módulo de Dados

## Pergunta investigada

**Onde as quedas de energia são mais frequentes ou mais demoradas, e o que pode explicar essa diferença?**

## Objetivo

Investigar, com base em dados públicos da ANEEL, quais estados brasileiros apresentam os
piores indicadores de continuidade de energia elétrica — tanto em **frequência** de
interrupções (FEC) quanto em **duração** (DEC) — e testar duas hipóteses explicativas:

1. **Hipótese climática**: meses/estados com mais chuva e vento forte concentram mais
   interrupções de origem externa e não programada (FECXN/DECXN).
2. **Hipótese populacional/geográfica**: municípios menores/menos populosos levam mais
   tempo para ter a energia restabelecida (DEC mais alto).

## Integrantes do grupo

- Luiz Ricardo Vigilato
- 
- 

## Perguntas de análise (guiam o dashboard)

| # | Pergunta | Indicador(es) usado(s) |
|---|---|---|
| 1 | Quais estados apresentam os maiores valores de DEC e FEC? | `DEC`, `FEC` |
| 2 | As interrupções são mais frequentes ou mais demoradas? | `FEC` vs `DEC` |
| 3 | Grande parte das interrupções é de origem externa (FECXN/DECXN)? | `FECXN`, `DECXN` vs `FEC`, `DEC` |
| 4 | Estados com maior índice de chuva apresentam maiores valores de DECXN/FECXN? | `DECXN`/`FECXN` x precipitação (INMET) |
| 5 | Municípios com menor população têm DEC (duração) maior? | `DEC` x população (IBGE) |

A conclusão do grupo (o que melhor explica as diferenças observadas) é apresentada na
etapa de apresentação, cruzando as respostas das 5 perguntas acima — não é um gráfico
isolado do dashboard.

## Fontes de dados

| Base | Fonte | Papel no projeto |
|---|---|---|
| Indicadores de Continuidade (DEC/FEC) | ANEEL — Dados Abertos ([dadosabertos.aneel.gov.br](https://dadosabertos.aneel.gov.br/dataset/indicadores-coletivos-de-continuidade-dec-e-fec)) | Base principal |
| IndQual Município (crosswalk conjunto → município) | ANEEL — Dados Abertos ([dadosabertos.aneel.gov.br/dataset/indqual-municipio](https://dadosabertos.aneel.gov.br/dataset/indqual-municipio)) | Chave de ligação para juntar a base principal ao IBGE |
| Estimativas de População nos Municípios | IBGE | Base complementar 1 — testa a hipótese populacional/geográfica |
| Dados meteorológicos por estação automática | INMET ([bdmep.inmet.gov.br](https://bdmep.inmet.gov.br)) | Base complementar 2 — testa a hipótese climática |

Detalhes de colunas, período coberto e limitações de cada base: ver
`documentacao/dicionario_de_dados.md`.

## Ferramentas usadas

- **Python (pandas)** — ETL e tratamento dos dados
- **Looker Studio** — dashboard final
- **Bibliotecas Python**: pandas, openpyxl (leitura do .xls/.xlsx do IBGE)

## Como executar o projeto

1. Coloque os arquivos originais nas pastas correspondentes (ver estrutura abaixo).
2. Baixe o crosswalk oficial `indqual-municipio.csv` do portal de dados abertos da ANEEL
   e salve em `documentacao/`.
3. Instale as dependências:
   ```bash
   pip install pandas openpyxl xlrd
   ```
4. Rode o ETL:
   ```bash
   cd etl
   python etl_quedas_energia.py
   ```
5. O resultado é gerado em `bases_tratadas/base_final_tratada.csv` — esse é o arquivo
   usado como fonte de dados no Looker Studio.

## Estrutura de pastas

```
projeto_final_grupo/
├── README.md
├── bases_originais/
│   ├── base_principal/                    <- CSV da ANEEL (DEC/FEC)
│   ├── base_complementar_01_ibge/         <- planilha de população
│   └── base_complementar_02_inmet/2025/   <- CSVs de cada estação do INMET
├── bases_tratadas/
│   └── base_final_tratada.csv             <- gerado pelo ETL, usado no dashboard
├── etl/
│   └── etl_quedas_energia.py
├── dashboard/
│   └── (link/instruções de acesso ao Looker Studio)
└── documentacao/
    ├── dicionario_de_dados.md
    └── indqual-municipio.csv              <- crosswalk oficial da ANEEL
```

## Limitações conhecidas

Ver seção "Limitações" em `documentacao/dicionario_de_dados.md` — em resumo: os
indicadores DEC/FEC são apurados por **conjunto elétrico**, não por município (um mesmo
conjunto pode cobrir várias cidades, que herdam o mesmo valor); e o clima é agregado por
**estado**, não por município, porque a malha de estações do INMET não cobre todas as
cidades.