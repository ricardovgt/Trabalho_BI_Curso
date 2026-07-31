# -*- coding: utf-8 -*-
"""
ETL - Projeto Final Módulo de Dados
Pergunta: Onde as quedas de energia são mais frequentes ou mais demoradas
          e o que pode explicar essa diferença?

Este script:
  1) Lê e trata a base principal da ANEEL (indicadores de continuidade DEC/FEC).
  2) Lê e trata a tabela oficial de ligação "conjunto elétrico -> município" da ANEEL.
  3) Lê e trata a base de população do IBGE.
  4) Lê, concatena e agrega (mensalmente, por estação) os arquivos do INMET.
  5) Junta tudo em uma única base final, pronta para o Power BI.

Saída: bases_tratadas/base_final_tratada.csv

Como rodar:
    python etl_quedas_energia.py

Ajuste os caminhos na seção CONFIGURAÇÃO abaixo antes de rodar com os dados reais.
"""

import glob
import os
import unicodedata

import pandas as pd

# =========================================================================
# CONFIGURAÇÃO — ajuste os caminhos para a estrutura real do projeto
# =========================================================================
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CAMINHO_BASE_PRINCIPAL = os.path.join(
    RAIZ, "bases_originais", "base_principal",
    "indicadores-continuidade-coletivos-2020-2029.csv"
)
CAMINHO_CROSSWALK_MUNICIPIO = os.path.join(
    RAIZ, "documentacao", "indqual-municipio.csv"
)
PASTA_POPULACAO_IBGE = os.path.join(RAIZ, "bases_originais", "base_complementar_01_ibge")
PASTA_INMET = os.path.join(
    RAIZ, "bases_originais", "base_complementar_02_inmet", "2025"
)
CAMINHO_SAIDA = os.path.join(RAIZ, "bases_tratadas", "base_final_tratada.csv")

# Ano-base da análise (o projeto quer só 2025)
ANO_ALVO = 2025

# Indicadores da ANEEL que vamos manter (ver dicionário dominio-indicadores.csv da ANEEL):
#   FEC/DEC     -> geral (frequência / duração)
#   FECXN/DECXN -> causa externa, não programada (a mais ligada a clima)
#   NumCon      -> número de consumidores do conjunto (usado como peso nas médias)
INDICADORES_DE_INTERESSE = ["FEC", "DEC", "FECXN", "DECXN", "NumCon"]

# Limiar simples para "dia com chuva forte" (mm por hora) - ajustem se quiserem outro critério
LIMIAR_CHUVA_FORTE_MM = 10.0


# =========================================================================
# FUNÇÕES AUXILIARES
# =========================================================================
def normaliza_texto(texto: str) -> str:
    """Remove acentos, espaços extras e deixa em maiúsculas. Útil para chaves de texto."""
    if pd.isna(texto):
        return texto
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII")
    return texto


def valor_br_para_float(serie: pd.Series) -> pd.Series:
    """Converte strings no formato brasileiro ('1,57') para float (1.57).
    Trata vazios/strings inválidas como NaN."""
    serie = serie.astype(str).str.strip()
    serie = serie.str.replace(".", "", regex=False)   # milhar, se houver
    serie = serie.str.replace(",", ".", regex=False)   # decimal
    return pd.to_numeric(serie, errors="coerce")


# =========================================================================
# 1) BASE PRINCIPAL (ANEEL - DEC/FEC)
# =========================================================================
def carregar_base_principal(caminho: str) -> pd.DataFrame:
    df = pd.read_csv(
        caminho,
        sep=";",
        encoding="utf-8",
        dtype=str,
        quotechar='"',
    )

    # Limpeza de nomes de coluna e espaços sobrando nas células de texto
    df.columns = [c.strip() for c in df.columns]
    for col in ["DscConjUndConsumidoras", "SigAgente", "SigIndicador"]:
        df[col] = df[col].str.strip()

    # Tipagem
    df["IdeConjUndConsumidoras"] = df["IdeConjUndConsumidoras"].astype(str).str.strip()
    df["AnoIndice"] = pd.to_numeric(df["AnoIndice"], errors="coerce").astype("Int64")
    df["NumPeriodoIndice"] = pd.to_numeric(df["NumPeriodoIndice"], errors="coerce").astype("Int64")
    df["VlrIndiceEnviado"] = valor_br_para_float(df["VlrIndiceEnviado"])

    n_antes = len(df)

    # Filtro 1: ano-alvo
    df = df[df["AnoIndice"] == ANO_ALVO]

    # Filtro 2: só os indicadores que interessam à análise
    df = df[df["SigIndicador"].isin(INDICADORES_DE_INTERESSE)]

    # Filtro 3: mês válido (1-12) e valor não nulo
    df = df[df["NumPeriodoIndice"].between(1, 12)]
    df = df.dropna(subset=["VlrIndiceEnviado"])

    print(f"[base_principal] linhas lidas: {n_antes} | após filtros (ano={ANO_ALVO}, "
          f"indicadores={INDICADORES_DE_INTERESSE}): {len(df)}")

    return df


# =========================================================================
# 2) CROSSWALK CONJUNTO -> MUNICÍPIO (ANEEL - IndQual Município)
# =========================================================================
def carregar_crosswalk_municipio(caminho: str) -> pd.DataFrame:
    df = pd.read_csv(caminho, sep=";", encoding="latin-1", dtype=str)
    df.columns = [c.strip() for c in df.columns]

    df["IdeConjUnidConsumidoras"] = df["IdeConjUnidConsumidoras"].astype(str).str.strip()
    df["CodMunicipio"] = df["CodMunicipio"].astype(str).str.strip()
    df["NomMunicipio"] = df["NomMunicipio"].str.strip()
    df["SigUF"] = df["SigUF"].str.strip()

    # Renomeia para bater com o nome de coluna da base principal na hora do join
    df = df.rename(columns={"IdeConjUnidConsumidoras": "IdeConjUndConsumidoras"})

    n_conjuntos = df["IdeConjUndConsumidoras"].nunique()
    n_municipios_por_conjunto = df.groupby("IdeConjUndConsumidoras")["CodMunicipio"].nunique()
    print(f"[crosswalk] {n_conjuntos} conjuntos | "
          f"{(n_municipios_por_conjunto > 1).sum()} deles cobrem mais de 1 município "
          f"(limitação a documentar: DEC/FEC desses conjuntos se repete em todas as cidades ligadas a eles)")

    return df[["IdeConjUndConsumidoras", "CodMunicipio", "NomMunicipio", "SigUF"]]


# =========================================================================
# 3) POPULAÇÃO (IBGE)
# =========================================================================
def encontrar_arquivo_ibge(pasta: str) -> str:
    """Procura o primeiro .xls ou .xlsx na pasta, sem depender do nome exato do arquivo."""
    candidatos = glob.glob(os.path.join(pasta, "*.xls")) + glob.glob(os.path.join(pasta, "*.xlsx"))
    if not candidatos:
        raise FileNotFoundError(
            f"Nenhum arquivo .xls/.xlsx encontrado em: {pasta}\n"
            f"Confira se o arquivo do IBGE está mesmo nessa pasta."
        )
    if len(candidatos) > 1:
        print(f"[ibge] AVISO: mais de um arquivo .xls/.xlsx encontrado em {pasta}, "
              f"usando o primeiro: {os.path.basename(candidatos[0])}")
    return candidatos[0]


def carregar_populacao_ibge(pasta: str) -> pd.DataFrame:
    caminho = encontrar_arquivo_ibge(pasta)
    print(f"[ibge] lendo arquivo: {os.path.basename(caminho)}")

    planilha = pd.ExcelFile(caminho)

    # Se houver aba com "município" no nome, tenta ela primeiro (planilhas do IBGE costumam
    # ter uma aba agregada por UF/Brasil e outra por município — queremos a segunda).
    abas_ordenadas = sorted(
        planilha.sheet_names,
        key=lambda nome: 0 if "MUNIC" in normaliza_texto(nome) else 1,
    )

    # O Brasil tem ~5.570 municípios. Uma aba "por UF" ou "Brasil" nunca vai chegar
    # nem perto disso, então usamos isso pra rejeitar a aba errada automaticamente.
    MINIMO_LINHAS_ESPERADO = 500

    df = None
    aba_usada = None
    linha_cabecalho = None

    for nome_aba in abas_ordenadas:
        bruto = planilha.parse(nome_aba, header=None, dtype=str)
        for i, linha in bruto.iterrows():
            texto_linha = " ".join(
                normaliza_texto(v) for v in linha.values if pd.notna(v)
            )
            # agora exige os 3 termos juntos na mesma linha, pra ser mais rigoroso
            if "COD" in texto_linha and "MUNIC" in texto_linha and "POPULA" in texto_linha:
                candidato = planilha.parse(nome_aba, header=i, dtype=str)
                candidato.columns = [normaliza_texto(c) for c in candidato.columns]
                cols_munic = [c for c in candidato.columns if "COD" in c and "MUNIC" in c]
                if cols_munic and candidato[cols_munic[0]].notna().sum() >= MINIMO_LINHAS_ESPERADO:
                    df = candidato
                    aba_usada = nome_aba
                    linha_cabecalho = i
                    break
                else:
                    n = candidato[cols_munic[0]].notna().sum() if cols_munic else 0
                    print(f"[ibge] aba '{nome_aba}' linha {i} tem cabeçalho parecido mas só "
                          f"{n} linhas de dado — provavelmente é a aba agregada por UF, pulando.")
        if df is not None:
            break

    if df is None:
        abas = ", ".join(planilha.sheet_names)
        raise ValueError(
            f"Não encontrei uma aba de município válida (abas disponíveis: {abas}). "
            f"Rode isso e me manda o resultado:\n"
            f"  import pandas as pd\n"
            f"  x = pd.ExcelFile(r'{caminho}')\n"
            f"  print(x.sheet_names)\n"
            f"  print(x.parse(x.sheet_names[-1], header=None).head(15))"
        )

    print(f"[ibge] cabeçalho encontrado na aba '{aba_usada}', linha {linha_cabecalho} "
          f"({len(df)} linhas de município)")
    df.columns = [normaliza_texto(c) for c in df.columns]

    # Nomes de coluna normalizados esperados: 'UF', 'COD. UF', 'COD. MUNIC',
    # 'NOME DO MUNICIPIO', 'POPULACAO ESTIMADA' (varia um pouco conforme o arquivo)
    col_cod_uf = [c for c in df.columns if "COD" in c and "UF" in c][0]
    col_cod_munic = [c for c in df.columns if "COD" in c and "MUNIC" in c][0]
    col_nome = [c for c in df.columns if "NOME" in c][0]
    col_pop = [c for c in df.columns if "POPULACAO" in c][0]

    df = df.dropna(subset=[col_cod_uf, col_cod_munic])

    # Código IBGE completo (7 dígitos) = 2 dígitos do UF + 5 dígitos do município
    df["CodMunicipio"] = (
        df[col_cod_uf].astype(str).str.extract(r"(\d+)")[0].str.zfill(2)
        + df[col_cod_munic].astype(str).str.extract(r"(\d+)")[0].str.zfill(5)
    )
    df["NomeMunicipioIBGE"] = df[col_nome].str.strip()
    df["PopulacaoEstimada"] = pd.to_numeric(
        df[col_pop].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )

    resultado = df[["CodMunicipio", "NomeMunicipioIBGE", "PopulacaoEstimada"]].dropna(
        subset=["PopulacaoEstimada"]
    )
    print(f"[ibge] {len(resultado)} municípios carregados")
    return resultado


# =========================================================================
# 4) CLIMA (INMET) — concatena todas as estações e agrega por mês
# =========================================================================
def ler_um_arquivo_inmet(caminho: str) -> pd.DataFrame:
    with open(caminho, encoding="latin-1") as f:
        linhas_meta = [next(f).strip() for _ in range(8)]

    meta = {}
    for linha in linhas_meta:
        if ":;" in linha:
            chave, valor = linha.split(":;", 1)
            meta[chave.strip().upper()] = valor.strip()

    dados = pd.read_csv(
        caminho,
        sep=";",
        encoding="latin-1",
        skiprows=8,
        decimal=",",
        na_values=["", " "],
    )
    dados.columns = [c.strip() for c in dados.columns]
    # remove eventual coluna fantasma criada pelo ; final de cada linha
    dados = dados.loc[:, ~dados.columns.str.match(r"^Unnamed")]

    col_precip = [c for c in dados.columns if "PRECIPITA" in c.upper()][0]
    col_rajada = [c for c in dados.columns if "RAJADA" in c.upper()][0]

    dados["Data"] = pd.to_datetime(dados["Data"], format="%Y/%m/%d", errors="coerce")
    dados["Ano"] = dados["Data"].dt.year
    dados["Mes"] = dados["Data"].dt.month

    dados["UF"] = meta.get("UF")
    dados["Estacao"] = meta.get("ESTACAO")
    dados["CodigoEstacao"] = meta.get("CODIGO (WMO)")
    dados["PrecipitacaoMM"] = pd.to_numeric(dados[col_precip], errors="coerce")
    dados["RajadaMaximaMS"] = pd.to_numeric(dados[col_rajada], errors="coerce")

    return dados[["UF", "Estacao", "CodigoEstacao", "Ano", "Mes", "PrecipitacaoMM", "RajadaMaximaMS"]]


def carregar_clima_inmet(pasta: str) -> pd.DataFrame:
    arquivos = glob.glob(os.path.join(pasta, "*.CSV")) + glob.glob(os.path.join(pasta, "*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV do INMET encontrado em: {pasta}")

    partes = []
    for caminho in arquivos:
        try:
            partes.append(ler_um_arquivo_inmet(caminho))
        except Exception as erro:
            print(f"[inmet] AVISO: falha ao ler {os.path.basename(caminho)}: {erro}")

    bruto = pd.concat(partes, ignore_index=True)
    bruto = bruto[bruto["Ano"] == ANO_ALVO]

    # Agregação: de horário -> mensal, por estação
    agregado_estacao = bruto.groupby(["UF", "Estacao", "CodigoEstacao", "Ano", "Mes"]).agg(
        PrecipitacaoTotalMM=("PrecipitacaoMM", "sum"),
        RajadaMaximaMS=("RajadaMaximaMS", "max"),
        HorasComChuvaForte=("PrecipitacaoMM", lambda s: (s >= LIMIAR_CHUVA_FORTE_MM).sum()),
    ).reset_index()

    # Agregação final: de estação -> estado (média simples entre as estações do estado)
    agregado_uf = agregado_estacao.groupby(["UF", "Ano", "Mes"]).agg(
        PrecipitacaoMediaMM=("PrecipitacaoTotalMM", "mean"),
        RajadaMaximaMS=("RajadaMaximaMS", "max"),
        HorasComChuvaForte=("HorasComChuvaForte", "sum"),
        NumEstacoes=("Estacao", "nunique"),
    ).reset_index()

    print(f"[inmet] {len(arquivos)} arquivos de estação | "
          f"{agregado_uf['UF'].nunique()} UFs cobertas | {len(agregado_uf)} linhas UF x mês")
    return agregado_uf


# =========================================================================
# 5) JUNÇÃO FINAL
# =========================================================================
def montar_base_final():
    base = carregar_base_principal(CAMINHO_BASE_PRINCIPAL)
    crosswalk = carregar_crosswalk_municipio(CAMINHO_CROSSWALK_MUNICIPIO)
    populacao = carregar_populacao_ibge(PASTA_POPULACAO_IBGE)
    clima_uf = carregar_clima_inmet(PASTA_INMET)

    # --- base principal + crosswalk (conjunto -> município/UF) ---
    base = base.merge(crosswalk, on="IdeConjUndConsumidoras", how="left")
    sem_municipio = base["CodMunicipio"].isna().sum()
    if sem_municipio:
        print(f"[join] AVISO: {sem_municipio} linhas da base principal não encontraram "
              f"município no crosswalk (conjunto não cadastrado na tabela de ligação).")

    # --- + população IBGE (pelo código do município) ---
    base = base.merge(populacao, on="CodMunicipio", how="left")
    sem_populacao = base["PopulacaoEstimada"].isna().sum()
    if sem_populacao:
        print(f"[join] AVISO: {sem_populacao} linhas sem população encontrada no IBGE "
              f"(código de município pode não ter batido - checar formatação).")

    # --- + clima (pela UF e mês) ---
    base = base.merge(
        clima_uf,
        left_on=["SigUF", "AnoIndice", "NumPeriodoIndice"],
        right_on=["UF", "Ano", "Mes"],
        how="left",
    )
    sem_clima = base["PrecipitacaoMediaMM"].isna().sum()
    if sem_clima:
        print(f"[join] AVISO: {sem_clima} linhas sem dado de clima batendo "
              f"(UF sem estação INMET carregada nesse mês, ou nome de UF divergente).")

    colunas_finais = [
        "IdeConjUndConsumidoras", "DscConjUndConsumidoras", "SigAgente",
        "CodMunicipio", "NomeMunicipioIBGE", "SigUF",
        "AnoIndice", "NumPeriodoIndice",
        "SigIndicador", "VlrIndiceEnviado",
        "PopulacaoEstimada",
        "PrecipitacaoMediaMM", "RajadaMaximaMS", "HorasComChuvaForte", "NumEstacoes",
    ]
    base_final = base[colunas_finais].rename(columns={
        "AnoIndice": "Ano",
        "NumPeriodoIndice": "Mes",
        "VlrIndiceEnviado": "ValorIndicador",
    })

    os.makedirs(os.path.dirname(CAMINHO_SAIDA), exist_ok=True)
    base_final.to_csv(CAMINHO_SAIDA, index=False, sep=";", decimal=",", encoding="utf-8")
    print(f"\n[ok] Base final salva em: {CAMINHO_SAIDA}")
    print(f"[ok] {len(base_final)} linhas, {base_final['SigIndicador'].nunique()} indicadores, "
          f"{base_final['SigUF'].nunique()} UFs")
    return base_final


if __name__ == "__main__":
    montar_base_final()