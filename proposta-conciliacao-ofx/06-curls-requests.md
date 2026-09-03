# Curls das Requisições do Processo de Conciliação (API Omie)

Coleção de `curl` de todas as chamadas usadas no fluxo de conciliação OFX → Omie.
Onde há input, o valor está **parametrizado** como variável de shell (`${VAR}`)
para você preencher antes de executar.

> Base de tudo: envelope JSON via POST, credenciais no corpo. Ver
> [`../docs-erp-omie/02-autenticacao-e-requisicoes.md`](../docs-erp-omie/02-autenticacao-e-requisicoes.md).
>
> **Sempre inspecione o corpo da resposta** — a Omie pode retornar erro de
> negócio com `faultstring`/`faultcode` mesmo em HTTP != 200.

---

## 0. Variáveis base (defina uma vez na sessão)

```bash
# --- Credenciais (NÃO versionar; use variáveis de ambiente / cofre) ---
export OMIE_APP_KEY="SEU_APP_KEY"
export OMIE_APP_SECRET="SEU_APP_SECRET"

# --- Host base da API ---
export OMIE_BASE="https://app.omie.com.br/api/v1"
```

---

## 0.1 Autenticação / validação de credenciais

> **Importante:** a API Omie **não possui um endpoint de autenticação separado**
> (não há login, token nem header `Authorization`). As credenciais
> `app_key`/`app_secret` são enviadas **no corpo de cada chamada**. Ver
> [`../docs-erp-omie/02-autenticacao-e-requisicoes.md`](../docs-erp-omie/02-autenticacao-e-requisicoes.md).
>
> Portanto, o "curl de autenticação" abaixo é, na prática, um **teste de
> credenciais**: faz a chamada mais leve possível (`ListarContasCorrentes` com 1
> registro) só para confirmar se o par de chaves é válido.
>
> - **Credencial válida** → HTTP 200 com corpo contendo as contas.
> - **Credencial inválida** → corpo com `faultstring` (ex.: `"... not authorized."`)
>   e `faultcode`.

### curl (teste de credenciais)

```bash
curl -sS -X POST "${OMIE_BASE}/geral/contacorrente/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "ListarContasCorrentes",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [
      {
        "pagina": 1,
        "registros_por_pagina": 1,
        "apenas_importado_api": "N"
      }
    ]
  }'
```

> Dica: para falhar rápido em scripts, verifique se a resposta contém
> `faultstring` antes de prosseguir com as demais chamadas.

---

## 1. ListarContasCorrentes — descobrir os `nCodCC` (setup / pendência P1)

Endpoint: `/geral/contacorrente/` · uso: mapear conta Stone e contas destino.

### Inputs (parâmetros)

```bash
export PAGINA="1"                    # página (inicia em 1)
export REGISTROS_POR_PAGINA="100"    # <= 100 recomendado
export APENAS_IMPORTADO_API="N"      # S / N
```

### curl

```bash
curl -sS -X POST "${OMIE_BASE}/geral/contacorrente/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "ListarContasCorrentes",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [
      {
        "pagina": '"${PAGINA}"',
        "registros_por_pagina": '"${REGISTROS_POR_PAGINA}"',
        "apenas_importado_api": "'"${APENAS_IMPORTADO_API}"'"
      }
    ]
  }'
```

> Da resposta, capture `nCodCC` de cada conta (Stone origem + contas destino de
> crédito/Pix/iFood) e preencha em `config/roteamento.json`.

---

## 1a. ListarCategorias — valores válidos de `cCodCateg` (setup)

Endpoint: `/geral/categorias/` · uso: descobrir o `codigo` de categoria que vai
em `detalhes.cCodCateg` do `IncluirLancCC`.

### Inputs (parâmetros)

```bash
export PAGINA_CAT="1"                # página (inicia em 1)
export REGISTROS_CAT="100"           # <= 100 recomendado
```

### curl

```bash
curl -sS -X POST "${OMIE_BASE}/geral/categorias/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "ListarCategorias",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [
      {
        "pagina": '"${PAGINA_CAT}"',
        "registros_por_pagina": '"${REGISTROS_CAT}"'
      }
    ]
  }'
```

> Da resposta, use o campo `codigo` (string 20) de cada categoria como valor de
> `cCodCateg`. Preencha os `ccodcateg: null` de `config/roteamento.json`.

---

## 1b. PesquisarTipoDocumento — valores válidos de `cTipo` (setup)

Endpoint: `/geral/tiposdoc/` · uso: descobrir o `codigo` de tipo de documento que
vai em `detalhes.cTipo` do `IncluirLancCC` (PIX, DIN, BOL, TED...).

### Inputs (parâmetros)

```bash
# Sem filtros retorna a lista completa. Filtros abaixo são opcionais.
export FILTRO_COD_TIPODOC=""         # opcional: código exato (string 5)
export FILTRO_DESC_TIPODOC=""        # opcional: descrição
```

### curl (lista completa)

```bash
curl -sS -X POST "${OMIE_BASE}/geral/tiposdoc/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "PesquisarTipoDocumento",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [ {} ]
  }'
```

> Da resposta, use o campo `codigo` (string 5) como valor de `cTipo`. Prefira
> sempre um código retornado por este endpoint em vez de "chutar" o valor.

---

## 2. IncluirLancCC — lançar crédito roteado (rota `credito_roteado`)

Endpoint: `/financas/contacorrentelancamentos/`

### Inputs (parâmetros)

```bash
# cCodIntLanc: string(20) obrigatória — âncora de idempotência.
# O FITID da Stone é UUID(36) e NÃO cabe: derive via hash determinístico.
# Ex.: 20 primeiros hex do sha256 do FITID (ver pendência P3.1).
export FITID="COLE_O_FITID_AQUI"
export CCODINTLANC="$(printf '%s' "${FITID}" | shasum -a 256 | cut -c1-20)"

export NCODCC_DESTINO="0"            # nCodCC da conta destino (do passo 1)
export DATA_LANC="dd/mm/aaaa"        # data do lançamento
export VALOR_LANC="0.00"             # valor (decimal, ponto)
export CCODCATEG=""                  # categoria Omie (opcional, do mapa)
export CTIPO="PIX"                   # DIN/BOL/TED/PIX...
export OBSERVACAO="Conciliacao OFX - FITID ${FITID}"
```

### curl

```bash
curl -sS -X POST "${OMIE_BASE}/financas/contacorrentelancamentos/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "IncluirLancCC",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [
      {
        "cCodIntLanc": "'"${CCODINTLANC}"'",
        "cabecalho": {
          "nCodCC": '"${NCODCC_DESTINO}"',
          "dDtLanc": "'"${DATA_LANC}"'",
          "nValorLanc": '"${VALOR_LANC}"'
        },
        "detalhes": {
          "cCodCateg": "'"${CCODCATEG}"'",
          "cTipo": "'"${CTIPO}"'",
          "cObsLanc": "'"${OBSERVACAO}"'"
        }
      }
    ]
  }'
```

> **Transferência entre contas** (variação): informe também
> `"transferencia": { "nCodCCDestino": <nCodCC> }`. Use quando o crédito for
> transferência entre contas do Omie em vez de lançamento avulso.

---

## 3. PesquisarLancamentos — localizar título a pagar (rota `baixa_conta_pagar`)

Endpoint: `/financas/pesquisartitulos/`

> **Correções confirmadas pelo WSDL oficial** (`/financas/pesquisartitulos/?WSDL`,
> tipo `ltPesquisarRequest`):
> - O `call` e **`PesquisarLancamentos`** (nao `PesquisarTitulos` — este retorna
>   `Method "PesquisarTitulos" not exists`).
> - Paginacao usa **`nPagina`** / **`nRegPorPagina`** (nao `pagina`/`registros_por_pagina`).
> - **Nao existe filtro `dDtVenc`** — as datas sao por INTERVALO: **`dDtVencDe`** /
>   **`dDtVencAte`** (idem emissao `dDtEmisDe/Ate`, previsao `dDtPrevDe/Ate`, etc.).
> - **Nao existe filtro `nValorTitulo`** no request — o valor so vem na resposta
>   (`cabecTitulo.nValorTitulo`). O matching por valor e feito no cliente, sobre
>   os titulos retornados.

### Inputs (parâmetros)

```bash
export CNATUREZA="P"                 # P (pagar) / R (receber)
export DT_VENC_DE="dd/mm/aaaa"       # inicio da janela de vencimento
export DT_VENC_ATE="dd/mm/aaaa"      # fim da janela de vencimento (pode = DT_VENC_DE)
export STATUS_TITULO="EMABERTO"      # EMABERTO/ATRASADO/LIQUIDADO...
export PAGINA_TIT="1"
export REGISTROS_TIT="20"
# valor NAO e filtro da API: usado so no matching client-side (do debito OFX).
export VALOR_TITULO="0.00"
```

### curl

```bash
curl -sS -X POST "${OMIE_BASE}/financas/pesquisartitulos/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "PesquisarLancamentos",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [
      {
        "nPagina": '"${PAGINA_TIT}"',
        "nRegPorPagina": '"${REGISTROS_TIT}"',
        "cNatureza": "'"${CNATUREZA}"'",
        "cStatus": "'"${STATUS_TITULO}"'",
        "dDtVencDe": "'"${DT_VENC_DE}"'",
        "dDtVencAte": "'"${DT_VENC_ATE}"'"
      }
    ]
  }'
```

> Regra: dos titulos retornados, filtre por valor (`cabecTitulo.nValorTitulo`
> == valor do debito). Exatamente 1 `EMABERTO` casando → baixa (passo 4).
> 0 ou >1 candidatos → fila manual. Capture o `nCodTitulo` do resultado.

---

## 4. LancarPagamento — baixar título a pagar (rota `baixa_conta_pagar`)

Endpoint: `/financas/contapagar/`

### Inputs (parâmetros)

```bash
export NCOD_TITULO="0"               # nCodTitulo (vindo do passo 3)
export VALOR_PAGO="0.00"             # valor pago
export DATA_BAIXA="dd/mm/aaaa"       # data da baixa
export ID_CONTA_CORRENTE="0"         # nCodCC de saída do pagamento
export OBS_BAIXA="Conciliacao OFX - FITID ${FITID}"
```

### curl

```bash
curl -sS -X POST "${OMIE_BASE}/financas/contapagar/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "LancarPagamento",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [
      {
        "codigo_lancamento": '"${NCOD_TITULO}"',
        "valor": '"${VALOR_PAGO}"',
        "data": "'"${DATA_BAIXA}"'",
        "id_conta_corrente": '"${ID_CONTA_CORRENTE}"',
        "observacao": "'"${OBS_BAIXA}"'"
      }
    ]
  }'
```

> Retorna `codigo_baixa` (âncora de rastreio). Atenção: se a conta tiver Fluxo de
> Aprovação configurado, a baixa pode não ser imediata (ver P3). Confirme os
> campos exatos na página logada do serviço.

---

## 5. ExtratoContaCorrente — conferência de saldo (somente leitura)

Endpoint: `/financas/extrato/`

### Inputs (parâmetros)

```bash
export NCODCC_CONFERENCIA="0"        # nCodCC da conta a conferir
export DT_INICIAL="dd/mm/aaaa"       # período inicial
export DT_FINAL="dd/mm/aaaa"         # período final
```

### curl

```bash
curl -sS -X POST "${OMIE_BASE}/financas/extrato/" \
  -H "Content-Type: application/json" \
  -d '{
    "call": "ExtratoContaCorrente",
    "app_key": "'"${OMIE_APP_KEY}"'",
    "app_secret": "'"${OMIE_APP_SECRET}"'",
    "param": [
      {
        "nCodCC": '"${NCODCC_CONFERENCIA}"',
        "dPeriodoInicial": "'"${DT_INICIAL}"'",
        "dPeriodoFinal": "'"${DT_FINAL}"'"
      }
    ]
  }'
```

> Compare `nSaldoAtual` (Omie) com o `LEDGERBAL` do OFX para validar o
> fechamento. Endpoint somente leitura — não cria nem concilia movimento.

---

## Resumo do fluxo

| # | Chamada | Endpoint | Quando |
|---|---------|----------|--------|
| 1 | `ListarContasCorrentes` | `/geral/contacorrente/` | Setup: descobrir `nCodCC` (P1) |
| 1a | `ListarCategorias` | `/geral/categorias/` | Setup: valores de `cCodCateg` |
| 1b | `PesquisarTipoDocumento` | `/geral/tiposdoc/` | Setup: valores de `cTipo` |
| 2 | `IncluirLancCC` | `/financas/contacorrentelancamentos/` | Crédito roteado |
| 3 | `PesquisarLancamentos` | `/financas/pesquisartitulos/` | Débito: achar título |
| 4 | `LancarPagamento` | `/financas/contapagar/` | Débito: baixar título |
| 5 | `ExtratoContaCorrente` | `/financas/extrato/` | Conferência de saldo |

> Notas de pendência que afetam os inputs acima: **P1** (obter `nCodCC`),
> **P3/P3.1** (idempotência e derivação FITID→`cCodIntLanc`), **P4** (débitos
> Pix de mão de obra) e **P6** (estornos). Ver
> [`04-pendencias.md`](./04-pendencias.md).
