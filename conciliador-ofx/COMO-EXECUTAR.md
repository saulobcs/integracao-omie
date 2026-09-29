# Como executar o conciliador (dry-run)

Guia do que é necessário para rodar o fluxo de conciliação OFX → Omie. O
conciliador lê um extrato OFX, aplica as regras de roteamento e gera um
relatório (CSV + JSON). Ele tem **dois modos** (ver seção 4):

- **`dry-run`** (padrão): consulta a API (leitura), mas **nunca** executa
  inclusão, baixa ou manutenção — as ações ficam como proposta no relatório. É o
  modo para validar as regras de roteamento.
- **`apply`**: modo de execução final, que **executa** as escritas no Omie.

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

## 2. Instalação automática

Rode o instalador do seu sistema, uma vez por máquina. Ele faz **tudo**
automaticamente: localiza o Python 3.9+ (e **instala** se não houver), cria o
ambiente virtual `.venv/`, atualiza o pip, instala as dependências
(`requirements.txt`) e prepara os arquivos `.env` (da raiz e de cada cliente) a
partir dos `.env.example` — **sem sobrescrever** os que já existirem. Ao final,
roda os testes como verificação.

Os instaladores ficam em `conciliador-ofx/instaladores/`, um pacote por sistema:

| Sistema | Instalador | Auto-instala o Python via |
|---------|-----------|---------------------------|
| macOS | `instaladores/macos/install.command` | Homebrew (instala o Homebrew se faltar) |
| Linux | `instaladores/linux/install.sh` | apt / dnf / yum / pacman / zypper |
| Windows | `instaladores/windows/install.bat` | winget |

```bash
# macOS (ou clique duas vezes em install.command no Finder)
conciliador-ofx/instaladores/macos/install.command

# Linux
conciliador-ofx/instaladores/linux/install.sh
```

```
# Windows: clique duas vezes em
conciliador-ofx\instaladores\windows\install.bat
```

> **Auto-instalação do Python:** se o Python não for encontrado, o instalador o
> instala pelo gerenciador do sistema (pode pedir senha de administrador). No
> Windows, após instalar via winget, pode ser necessário reabrir o terminal e
> rodar o instalador de novo (o PATH só atualiza em uma nova sessão).

Fica pendente **apenas** o preenchimento manual das credenciais nos `.env`
(seção 2.1). Reexecutar o instalador é seguro: ele reutiliza o `.venv` e nunca
sobrescreve `.env` existentes.

> A pasta `.venv/` e os `.env` são locais e já ignorados pelo Git. Os comandos
> deste guia usam diretamente o interpretador dentro de `.venv`, sem precisar
> ativá-lo.

### 2.1 Preencher as credenciais (manual)

O instalador cria os `.env` vazios. Edite cada um com as chaves do Omie:

- **Raiz** (`.env`): uso single/CLI sem `--cliente`.
- **Por cliente** (`clientes/<id>/.env`): uso multicliente. O instalador lista,
  ao final, quais foram criados.

### Interface gráfica e lançadores

Para a execução sem comandos de conciliação, use a interface local no navegador
(`conciliador_web.py`). O lançador abre a página automaticamente; ela permite
escolher o OFX, mostra o resumo ao término e só oferece os modos seguros
`offline` e `dry-run`. O modo `apply` continua restrito à linha de comando com
`--confirmar`.

| Sistema | Arquivo para abrir |
|---------|--------------------|
| Windows | `executar_conciliador.bat` |
| macOS | `executar_conciliador.command` |
| Linux | `executar_conciliador.sh` |

No macOS e Linux, dê permissão de execução ao lançador uma única vez:

```bash
chmod +x executar_conciliador.sh executar_conciliador.command
```

---

## 3. Configurar as credenciais (`.env`)

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

## 4. Modelo de segurança (por modo)

O `OmieClient` tem duas allow-lists em `conciliador/omie_client.py`:

- **Leitura** (`METODOS_LEITURA`): `PesquisarLancamentos`, `ConsultarCliente`,
  `ListarClientes`, `ListarContasCorrentes`, `ListarCategorias`,
  `PesquisarTipoDocumento`, `ExtratoContaCorrente`, `ConsultaLancCC`,
  `ListarLancCC`.
- **Escrita** (`METODOS_ESCRITA`): `IncluirLancCC`, `LancarPagamento`.

O que cada modo pode fazer:

- **`dry-run` / `offline`** — o cliente é **somente leitura**
  (`somente_leitura=True`). Qualquer método de escrita é **bloqueado antes de
  qualquer chamada de rede**. As inclusões/baixas aparecem no relatório apenas
  como propostas descritivas (`baixa_proposta`, `IncluirLancCC` "apto a
  incluir"), nunca executadas.
- **`apply`** — o cliente é **read-write** (`somente_leitura=False`), o que
  libera **apenas** os métodos de `METODOS_ESCRITA` (mapeados). Verbos não
  mapeados (`Alterar*`, `Excluir*`, etc.) continuam bloqueados em qualquer modo.

A garantia read-only do dry-run e a liberação controlada do apply são travadas
por testes automatizados (ver seção 6).

---

## 5. Executar

A partir da pasta `conciliador-ofx/`:

```bash
# macOS: com os caminhos padrão (extrato de referência)
.venv/bin/python main.py

# macOS: apontando para um extrato específico
.venv/bin/python main.py \
  --ofx "../arquivos-referencia/Stone.ofx" \
  --config config/roteamento.json \
  --saida saida
```

No Windows PowerShell, substitua `.venv/bin/python` por
`.venv\Scripts\python.exe` nos comandos abaixo.

### Argumentos

| Argumento | Padrão | Descrição |
|-----------|--------|-----------|
| `--ofx` | `../arquivos-referencia/Comprovante de Extrato.ofx` | Caminho do arquivo OFX a processar. |
| `--config` | `config/roteamento.json` | Mapa de roteamento (origens e regras). |
| `--saida` | `saida/` | Pasta onde os relatórios são gravados. |
| `--modo` | `dry-run` | Modo de execução: `dry-run`, `apply` ou `offline` (ver abaixo). |
| `--confirmar` | (desligado) | **Obrigatório** no `--modo apply`. Confirma que você quer executar escritas reais no Omie. |

### Modos de execução

| Modo | API | Escreve no Omie? | Uso |
|------|-----|------------------|-----|
| `dry-run` (padrão) | consulta (leitura) | **Não** | Validar as regras de roteamento com dados reais (idempotência de crédito e matching de débito), sem risco. |
| `offline` | nenhuma | **Não** | Ver só o roteamento, sem rede. Não exige `.env`. |
| `apply` | leitura + **escrita** | **Sim** | Execução final: inclui lançamentos (`IncluirLancCC`) e baixa títulos (`LancarPagamento`). |

```bash
# dry-run (padrão): consulta, não escreve
.venv/bin/python main.py --ofx "../arquivos-referencia/Stone.ofx"

# offline: sem nenhuma chamada à API
.venv/bin/python main.py --ofx "../arquivos-referencia/Stone.ofx" --modo offline

# apply: EXECUÇÃO REAL (exige --confirmar)
.venv/bin/python main.py --ofx "../arquivos-referencia/Stone.ofx" --modo apply --confirmar
```

> **`apply` é escrita real.** Sem `--confirmar`, o programa aborta com aviso. O
> modo respeita idempotência: um crédito que já existe no Omie (mesmo
> `cCodIntLanc`) **não** é reincluído.

> **Desempenho:** com API (dry-run ou apply), o crédito faz uma consulta
> `ConsultaLancCC` por transação (idempotência) e o débito faz
> `PesquisarLancamentos` + `ConsultarCliente`. Em extratos grandes isso deixa a
> execução mais lenta. Use `--modo offline` quando só quiser ver o roteamento.

---

## 6. Saída

Cada execução gera dois arquivos em `saida/` com timestamp:

- `conciliacao_AAAAMMDD_HHMMSS.csv` — uma linha por transação.
- `conciliacao_AAAAMMDD_HHMMSS.json` — mesmo conteúdo + resumo e payloads
  propostos detalhados.

A pasta `saida/` é ignorada pelo Git.

O resumo também é impresso no terminal: total de transações, agrupamento por
rota (crédito roteado / baixa de conta a pagar / manual) e por regra.

---

## 7. Testes

```bash
cd conciliador-ofx
.venv/bin/python -m unittest discover -s tests -v
```

Os testes cobrem:

- **Garantia read-only do dry-run** (`test_dry_run_read_only.py`): no modo
  somente leitura a escrita é bloqueada antes da rede e um dry-run completo só
  emite chamadas de leitura; no modo read-write só os métodos de escrita
  mapeados são liberados.
- **Modo apply** (`test_executor_apply.py`): o `ExecutorApply` exige cliente
  read-write, executa a inclusão quando o crédito não existe e **não** reinclui
  quando já existe (idempotência); o `ExecutorDryRun` nunca executa escrita.

---

## 8. O que preparar antes de conciliar um extrato novo

1. **Preencher/ajustar `config/roteamento.json`** para a conta de origem:
   identificação (`BANKID`/`ACCTID`), `nCodCC` de origem e destinos, e as regras
   de crédito/débito por MEMO. Os `nCodCC` das contas vêm do
   `arquivos-referencia/contas-haru.json` (ou de `ListarContasCorrentes`).
2. **Preencher o `.env`** se quiser rodar com consulta à API.
3. **Rodar** com `--ofx` apontando para o extrato.
4. **Revisar** o relatório: transações em rota `manual` exigem tratamento
   humano.
