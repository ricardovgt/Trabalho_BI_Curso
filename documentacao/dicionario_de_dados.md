# Dicionário de Dados

## 1. Base principal — Indicadores de Continuidade (ANEEL)

- **Fonte**: ANEEL, Portal de Dados Abertos — *Indicadores Coletivos de Continuidade (DEC e FEC)*
  https://dadosabertos.aneel.gov.br/dataset/indicadores-coletivos-de-continuidade-dec-e-fec
- **Arquivo**: `indicadores-continuidade-coletivos-2020-2029.csv`
- **Período coberto**: 2020–2029 (usamos apenas `AnoIndice = 2025`)
- **Granularidade**: mensal, por **conjunto de unidades consumidoras** (subdivisão da
  área de concessão de uma distribuidora — não é o mesmo que município, ver Limitações)
- **Formato**: CSV, separador `;`, decimal `,`, encoding UTF-8

| Coluna | Tipo | Descrição |
|---|---|---|
| `DatGeracaoConjuntoDados` | data | Data de geração/publicação do arquivo |
| `IdeConjUndConsumidoras` | texto | Identificador do conjunto de unidades consumidoras (chave de junção com o crosswalk de município) |
| `DscConjUndConsumidoras` | texto | Nome/descrição do conjunto (não usar como chave — nomes têm variação de formatação) |
| `SigAgente` | texto | Sigla da distribuidora responsável |
| `NumCNPJ` | texto | CNPJ da distribuidora |
| `SigIndicador` | texto | Sigla do indicador apurado (ver tabela abaixo) |
| `AnoIndice` | inteiro | Ano de competência do índice |
| `NumPeriodoIndice` | inteiro (1–12) | Mês de competência do índice |
| `VlrIndiceEnviado` | decimal | Valor apurado do indicador |

### Indicadores da base tratada (`SigIndicador`)

Fonte: dicionário oficial `dominio-indicadores.csv` da ANEEL.

| Sigla | Significado | Usado no dashboard final? |
|---|---|---|
| `FEC` | Frequência Equivalente de Interrupção por unidade consumidora — geral | **Sim** — perguntas 2 e 3 |
| `DEC` | Duração Equivalente de Interrupção por unidade consumidora — geral | **Sim** — perguntas 1 e 4 |
| `FECXN` | Frequência de interrupções de origem externa, não programada | Fica disponível na base tratada, mas não é o foco dos gráficos finais |
| `DECXN` | Duração de interrupções de origem externa, não programada | Idem |
| `NumCon` | Número de consumidores do conjunto | Idem — disponível para eventuais médias ponderadas |

`DEC` e `FEC` foram os indicadores priorizados porque são os indicados diretamente pelo
material de orientação do professor. Outras siglas presentes na base (`FECIP`, `DECIND`,
`FECXP` etc., ligadas a causas internas e a interrupções programadas) não fazem parte do
escopo do projeto.

---

## 2. Crosswalk conjunto → município (ANEEL)

- **Fonte**: ANEEL, Portal de Dados Abertos — *IndQual Município*
  https://dadosabertos.aneel.gov.br/dataset/indqual-municipio
- **Arquivo**: `indqual-municipio.csv`
- **Papel**: liga `IdeConjUndConsumidoras` (base principal) ao código de município do
  IBGE, permitindo juntar com a base de população
- **Formato**: CSV, separador `;`, encoding Latin-1 (ISO-8859-1)

| Coluna | Tipo | Descrição |
|---|---|---|
| `IdeConjUnidConsumidoras` | texto | Mesmo identificador de conjunto da base principal |
| `CodMunicipio` | texto (7 dígitos) | Código IBGE do município |
| `NomMunicipio` | texto | Nome do município |
| `SigUF` | texto | UF do município |

---

## 3. Base complementar 1 — População (IBGE)

- **Fonte**: IBGE — Estimativas da População Residente nos Municípios Brasileiros
- **Arquivo**: `POP2025_20260113.xls`
- **Referência**: 1º de julho de 2025
- **Papel**: testar a hipótese de que municípios menores/menos populosos demoram mais
  para ter a energia restabelecida (proxy de "cidade pequena/rural") — pergunta 4

| Coluna (original) | Coluna tratada | Descrição |
|---|---|---|
| `UF` | — | Unidade da Federação |
| `COD. UF` + `COD. MUNIC` | `CodMunicipio` | Concatenados e zero-padded para formar o código IBGE de 7 dígitos (chave de junção) |
| `NOME DO MUNICÍPIO` | `NomeMunicipioIBGE` | Nome do município |
| `POPULAÇÃO ESTIMADA` | `PopulacaoEstimada` | População estimada |

---

## 4. Base complementar 2 — Clima (INMET)

- **Fonte**: INMET — Dados Históricos, Estações Automáticas
  https://bdmep.inmet.gov.br
- **Arquivos**: 1 CSV por estação/polo meteorológico, ano de 2025
- **Papel**: testar a hipótese de que estados com mais chuva têm mais interrupções
  (pergunta 3)
- **Formato**: CSV, separador `;`, decimal `,`, encoding Latin-1 (ISO-8859-1). Cada
  arquivo tem 8 linhas de metadado antes do cabeçalho das colunas de dados.

### Metadados (8 primeiras linhas do arquivo)

`REGIAO`, `UF`, `ESTACAO`, `CODIGO (WMO)`, `LATITUDE`, `LONGITUDE`, `ALTITUDE`,
`DATA DE FUNDACAO`

### Colunas de dados (horárias)

| Coluna (original) | Usada no projeto? | Observação |
|---|---|---|
| `Data` | Sim | Combinada com `Hora UTC` |
| `Hora UTC` | Indiretamente | Usada para saber que a granularidade é horária, antes de agregar por mês |
| `PRECIPITAÇÃO TOTAL, HORÁRIO (mm)` | **Sim** | Agregada por soma mensal → `PrecipitacaoTotalMM`; também usada para contar horas com chuva forte (≥ 10 mm/h) |
| `PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB)` | Não | Fora do escopo da análise |
| `PRESSÃO ATMOSFERICA MAX./MIN. NA HORA ANT. (mB)` | Não | Idem |
| `RADIACAO GLOBAL (Kj/m²)` | Não | Idem |
| `TEMPERATURA ...` (7 colunas) | Não | Idem |
| `UMIDADE ...` (3 colunas) | Não | Idem |
| `VENTO, DIREÇÃO HORARIA (gr)` | Não | Idem |
| `VENTO, RAJADA MAXIMA (m/s)` | Disponível na base tratada | Não usada nos gráficos finais |
| `VENTO, VELOCIDADE HORARIA (m/s)` | Não | Idem |

### Agregação aplicada

1. Horário → mensal, por estação: soma de chuva, máximo de rajada, contagem de horas
   com chuva ≥ 10 mm.
2. Mensal por estação → mensal por estado (UF): média entre as estações do estado.
   (Justificativa: a malha do INMET não tem uma estação por município, então o nível de
   estado é o que garante cobertura suficiente para comparar com a base principal.)

**Importante**: por essa agregação, a variável de precipitação é a mesma para todos os
municípios de um mesmo estado no mesmo mês. Isso é levado em conta na pergunta 3, que
compara precipitação **por estado**, não por município individual.

---

## Chaves de junção usadas no ETL

| Junção | Chave |
|---|---|
| Base principal ↔ Crosswalk município | `IdeConjUndConsumidoras` |
| Base principal (+crosswalk) ↔ IBGE | `CodMunicipio` |
| Base principal ↔ INMET (agregado por UF) | `SigUF` + `Ano` + `Mes` |

---

## Limitações encontradas

1. **Granularidade "conjunto" ≠ "município"**: os indicadores DEC/FEC são apurados por
   conjunto elétrico. Um mesmo conjunto pode cobrir vários municípios (encontramos casos
   de conjuntos cobrindo mais de 15 cidades), que recebem exatamente o mesmo valor de
   DEC/FEC. Isso significa que comparações **entre municípios de um mesmo conjunto** não
   revelam diferença real — a comparação é mais confiável no nível de conjunto/estado.

2. **Clima agregado por estado, não por município**: como as estações do INMET não
   cobrem todos os municípios, a variável climática foi trazida para o nível de UF. Por
   isso, a pergunta 3 compara precipitação por **estado**, e não por município.

3. **Período de referência da população**: a estimativa do IBGE é de 1º/jul/2025; os
   indicadores de continuidade cobrem o ano inteiro de 2025. Não há defasagem
   significativa, mas vale registrar.

4. **Cobertura incompleta em alguns cruzamentos**: nem todo conjunto tem um município
   correspondente no crosswalk, nem toda UF necessariamente teve estação INMET ativa em
   todos os meses. O script de ETL imprime a contagem de linhas afetadas em cada junção
   para que isso seja monitorado.

5. **Indicadores disponíveis mas não usados nos gráficos finais**: a base tratada mantém
   `FECXN`, `DECXN` e `NumCon` (útil para eventuais médias ponderadas), mas o dashboard
   final se concentra em `DEC` e `FEC`, conforme indicado pelo material do professor.