# Como executar o conciliador (dry-run)

Guia do que é necessário para rodar o fluxo de conciliação OFX → Omie. O
conciliador roda em **dry-run**: lê um extrato OFX, aplica as regras de
roteamento e gera um relatório (CSV + JSON) com as ações que **seriam**
executadas no Omie. Ele **nunca** executa inclusão, baixa ou manutenção — apenas
consulta (leitura) a API quando há credenciais.

---

## 1. Pré-requisitos

| Requisito | Detalhe |
|-----------|---------|
| **Python 3.9+** | O projeto usa apenas a biblioteca padrão (stdlib). **Não** há dependências externas (`requests`, `python-dotenv`, etc.) para instalar. |
| **Arquivo OFX** | O extrato bancário a conciliar (ex.: extrato da Stone). |
| **`config/roteamento.json`** | Mapa de regras por conta de origem (já versionado). |
| **Credenciais Omie** (opcional) | `app_key`/`app_secret` no `.env`. Só necessárias para a etapa de **consulta** à API (matching de débito e checagem de idempotência do crédito). Sem elas, o fluxo roda em modo offline. |

> A API Omie **não** tem endpoint de autenticação separado: as credenciais vão
> no corpo de cada chamada. Elas são geradas no próprio Omie ao cadastrar um
> aplicativo/integração.

---

## 2. Configurar as credenciais (`.env`)

As credenciais ficam num arquivo `.env` na raiz de `conciliador-ofx/`. Esse
arquivo **não é versionado** (está no `.gitignore`). Há um modelo em
[`.env.example`](./.env.example).

```bash
cd conciliador-ofx
cp .env.example .env
# edite .env e preencha OMIE_APP_KEY e OMIE_APP_SECRET
```

Conteúdo do `.env`:

```dotenv
OMIE_APP_KEY=seu_app_key
OMIE_APP_SECRET=seu_app_secret
OMIE_BASE=https://app.omie.com.br/api/v1
```

- **Precedência:** variáveis de ambiente do processo têm prioridade sobre o
  `.env` (permite override pontual, ex.: `OMIE_APP_KEY=... python3 main.py`).
- **Sem credenciais:** o fluxo ainda roda, mas as etapas que dependem da API
  (matching de débito e idempotência do crédito) ficam apenas como "payload
  proposto" — nada é consultado.

---

## 3. Modelo de segurança (read-only)

Mesmo com credenciais válidas, o conciliador é **somente leitura**:

- O `OmieClient` só aceita métodos de **consulta/pesquisa** (allow-list em
  `conciliador/omie_client.py`): `PesquisarLancamentos`, `ConsultarCliente`,
  `ListarClientes`, `ListarContasCorrentes`, `ListarCategorias`,
  `PesquisarTipoDocumento`, `ExtratoContaCorrente`, `ConsultaLancCC`,
  `ListarLancCC`.
- Qualquer método de **escrita** (`IncluirLancCC`, `LancarPagamento`,
  `Incluir*`, `Alterar*`, `Excluir*`) é **bloqueado antes de qualquer chamada de
  rede**.
- As baixas/inclusões aparecem no relatório apenas como propostas descritivas
  (`baixa_proposta`, `IncluirLancCC` "apto a incluir"), nunca executadas.

Essa garantia é travada por testes automatizados (ver seção 6).

---

## 4. Executar

A partir da pasta `conciliador-ofx/`:

```bash
# Com os caminhos padrão (extrato de referência)
python3 main.py

# Apontando para um extrato específico
python3 main.py \
  --ofx "../arquivos-referencia/Stone.ofx" \
  --config config/roteamento.json \
  --saida saida
```

### Argumentos

| Argumento | Padrão | Descrição |
|-----------|--------|-----------|
| `--ofx` | `../arquivos-referencia/Comprovante de Extrato.ofx` | Caminho do arquivo OFX a processar. |
| `--config` | `config/roteamento.json` | Mapa de roteamento (origens e regras). |
| `--saida` | `saida/` | Pasta onde os relatórios são gravados. |
| `--sem-api` | (desligado) | Força o modo offline: **não** consulta a API, mesmo com `.env` preenchido. Útil para rodar rápido, sem rede. |

> **Desempenho:** com credenciais, o crédito faz uma consulta `ConsultaLancCC`
> por transação (checagem de idempotência) e o débito faz `PesquisarLancamentos`
> + `ConsultarCliente`. Em extratos grandes isso deixa a execução mais lenta. Use
> `--sem-api` quando só quiser ver o roteamento.

---

## 5. Saída

Cada execução gera dois arquivos em `saida/` com timestamp:

- `conciliacao_AAAAMMDD_HHMMSS.csv` — uma linha por transação.
- `conciliacao_AAAAMMDD_HHMMSS.json` — mesmo conteúdo + resumo e payloads
  propostos detalhados.

A pasta `saida/` é ignorada pelo Git.

O resumo também é impresso no terminal: total de transações, agrupamento por
rota (crédito roteado / baixa de conta a pagar / manual) e por regra.

---

## 6. Testes (garantia read-only)

Para confirmar que nenhum serviço de escrita é chamado:

```bash
cd conciliador-ofx
python3 -m unittest discover -s tests -v
```

Os testes provam que a allow-list não contém métodos de escrita, que a escrita é
bloqueada antes da rede, e que um dry-run completo só emite chamadas de leitura.

---

## 7. O que preparar antes de conciliar um extrato novo

1. **Preencher/ajustar `config/roteamento.json`** para a conta de origem:
   identificação (`BANKID`/`ACCTID`), `nCodCC` de origem e destinos, e as regras
   de crédito/débito por MEMO. Os `nCodCC` das contas vêm do
   `arquivos-referencia/contas-haru.json` (ou de `ListarContasCorrentes`).
2. **Preencher o `.env`** se quiser rodar com consulta à API.
3. **Rodar** com `--ofx` apontando para o extrato.
4. **Revisar** o relatório: transações em rota `manual` exigem tratamento
   humano.
