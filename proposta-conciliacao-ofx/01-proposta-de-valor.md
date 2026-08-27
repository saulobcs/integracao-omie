# Proposta de Valor — Conciliação OFX x Omie via API

Documento de entendimento para automatizar a conciliação entre o extrato
bancário (arquivo **OFX**) e os lançamentos financeiros no **Omie ERP**, usando a
API de integração.

> Base: documentação interna em [`../docs-erp-omie/`](../docs-erp-omie/) e
> confirmação nas páginas oficiais do [Portal do Desenvolvedor Omie](https://developer.omie.com.br/service-list/)
> e da Central de Ajuda Omie. Conteúdo reescrito para documentação interna.

---

## 1. Problema atual (fluxo manual)

Hoje a conciliação é feita inteiramente na tela do Omie:

1. Exporta-se o extrato do banco por período (arquivo).
2. Faz-se o **upload do extrato** na tela de Conciliação Bancária do Omie.
3. Os apontamentos de conciliação são feitos **1 a 1**, casando cada movimento
   do extrato com o lançamento correspondente no sistema.

O gargalo é a etapa 3: o apontamento manual, repetitivo e sujeito a erro.

---

## 2. Restrições confirmadas na documentação da Omie

Duas descobertas definem o desenho da solução:

- **A API REST da Omie NÃO expõe serviço de upload de extrato nem de conciliação
  bancária.** A [lista oficial de serviços](https://developer.omie.com.br/service-list/)
  não contém nenhum endpoint de "importar extrato" ou "conciliar extrato x
  lançamento". Essa funcionalidade existe apenas na **tela** (importação manual
  de OFX) ou via **Integração Bancária Automática** dos bancos parceiros.
- **A importação de extrato para conciliação aceita exclusivamente arquivos OFX**
  (não CSV, PDF, XLS) — conforme a Central de Ajuda Omie.

### Decisões do projeto

| Decisão | Definição |
|---------|-----------|
| Tela formal de Conciliação Bancária | **Não é obrigatória** |
| Conexão direta banco ↔ Omie (Integração Automática) | **Descartada** (não é opção) |
| Formato de origem do extrato | **OFX do banco** |
| Objetivo central | Extrato refletido corretamente nos lançamentos, com **rastreio** e **idempotência** |

**Conclusão:** o único caminho viável é a **conciliação por baixa de título,
dirigida pelo OFX** — a aplicação lê o OFX e executa as baixas/lançamentos via
API. Isso NÃO alimenta a tela nativa de Conciliação Bancária, mas produz efeito
financeiro equivalente (título quitado, saldo da conta corrente movimentado).

---

## 3. Proposta de valor

- **Elimina o apontamento manual 1 a 1**, que é o principal consumidor de tempo.
- **Rastreabilidade ponta a ponta:** cada linha do OFX fica vinculada ao
  lançamento e à baixa gerados no Omie.
- **Idempotência:** reprocessar o mesmo OFX não gera baixas duplicadas.
- **Tratamento explícito de exceções:** casos ambíguos vão para uma fila de
  revisão humana, em vez de baixa incorreta.
- **Conferência automática de saldo** entre o extrato e o Omie ao final.

---

## 4. Arquitetura do fluxo

```
OFX do banco
   │  parse
   ▼
Transações normalizadas (fitid, data, valor, sinal, memo)
   │  para cada transação
   ▼
[1] Já processada?  ──sim──►  pula (idempotência)
   │ não
   ▼
[2] Match: PesquisarTitulos / ListarMovimentos
   │
   ├─ 1 título casado  ──►  [3] Baixa (LancarRecebimento / baixa CP)
   ├─ sem título        ──►  IncluirLancCC (tarifa/IOF/rendimento) OU fila de exceção
   └─ múltiplos/parcial ──►  fila de exceção (revisão humana)
   ▼
[4] Persistir vínculo: fitid ⇄ codigo_lancamento + codigo_baixa
   ▼
[5] Conferência: ExtratoContaCorrente (saldo Omie x saldo OFX)
```

---

## 5. Classificação de cada linha do OFX

O "reflexo correto" depende de classificar cada transação em um destes caminhos:

| Tipo de linha OFX | Ação no Omie | Método / Endpoint |
|-------------------|--------------|-------------------|
| Crédito que casa com título a receber | Baixa do recebimento | `LancarRecebimento` — `/api/v1/financas/contareceber/` |
| Débito que casa com título a pagar | Baixa do pagamento | baixa via `/api/v1/financas/contapagar/` |
| Tarifa, IOF, rendimento (sem título) | Lançamento avulso categorizado | `IncluirLancCC` — `/api/v1/financas/contacorrentelancamentos/` |
| Transferência entre contas próprias | Lançamento de transferência | `IncluirLancCC` com `transferencia.nCodCCDestino` |
| Ambíguo (parcial, agrupado, sem match) | **Não baixa** — fila de exceção | revisão humana |

**Regra de ouro:** na dúvida, não baixe. Baixa incorreta é pior que baixa não
feita.

---

## 6. Rastreio e idempotência

### Rastreio

- `LancarRecebimento` retorna `codigo_lancamento` e `codigo_baixa`; o
  `codigo_baixa` é o identificador exclusivo daquela baixa
  ([doc oficial](https://ajuda.omie.com.br/pt-BR/articles/8255357-baixando-uma-conta-a-receber-via-api)).
- A baixa de contas a pagar segue o mesmo padrão
  ([doc oficial](https://ajuda.omie.com.br/pt-BR/articles/8257476-baixando-uma-conta-a-pagar-via-api)).
- O **`FITID`** (identificador único de cada transação dentro do OFX) é o âncora
  de rastreio. Persistir a tabela de vínculo:

  ```
  FITID (OFX)  ⇄  codigo_lancamento + codigo_baixa (Omie)
  ```

### Idempotência (duas camadas)

1. **Do lado da aplicação (barreira principal):** antes de baixar, consultar a
   tabela de vínculo pelo `FITID`. Se já existe, pular. Não depende do
   comportamento da API — é a garantia real.
2. **Do lado Omie (reforço):** usar o campo de "código de integração" que muitos
   recursos aceitam para correlacionar registros e viabilizar upsert (ver
   [`../docs-erp-omie/04-boas-praticas.md`](../docs-erp-omie/04-boas-praticas.md),
   seção 6). **A confirmar:** se `LancarRecebimento` aceita código de integração
   da baixa para enviar o `FITID` e obter idempotência server-side.

---

## 7. Serviços da API envolvidos

| Finalidade | Serviço | Endpoint |
|------------|---------|----------|
| Localizar título por valor/data/documento | `PesquisarTitulos` | `/api/v1/financas/pesquisartitulos/` |
| Varredura de movimentos por período/conta | `ListarMovimentos` | `/api/v1/financas/mf/` |
| Baixar título a receber | `LancarRecebimento` | `/api/v1/financas/contareceber/` |
| Baixar título a pagar | baixa (bloco `pagamento`) | `/api/v1/financas/contapagar/` |
| Lançamento avulso (tarifa/transferência) | `IncluirLancCC` | `/api/v1/financas/contacorrentelancamentos/` |
| Conferência de saldo | `ExtratoContaCorrente` | `/api/v1/financas/extrato/` |

Envelope de requisição, autenticação e paginação: ver
[`../docs-erp-omie/02-autenticacao-e-requisicoes.md`](../docs-erp-omie/02-autenticacao-e-requisicoes.md).

---

## 8. Riscos e pontos de atenção

- **Matching imperfeito:** valor + data resolve o trivial; parciais,
  agrupamentos (um crédito quita N boletos), juros/multa/desconto e defasagem de
  data exigem regras de tolerância e fila de exceção.
- **Boas práticas Omie:** baixar títulos existentes é o uso correto; evitar criar
  lançamentos avulsos (`IncluirLancCC`) para o que deveria ter documento de
  origem (ver `04-boas-praticas.md`, seção 4). Restringir `IncluirLancCC` a
  tarifas/rendimentos/transferências.
- **Erros de negócio com HTTP não-2xx:** tratar `faultstring`, diferenciar
  credencial / parâmetro / negócio; retry com backoff apenas para falhas
  transitórias, nunca para erro de negócio.
- **Parâmetros a confirmar na página logada do serviço:** campo de código de
  integração da baixa e a identificação exata do título (`codigo_lancamento` do
  título vs. código de integração).

---

## 9. Próximos passos

1. Confirmar, na página logada do serviço, os parâmetros de idempotência e
   identificação do título em `LancarRecebimento` e na baixa de contas a pagar.
2. Prototipar em Python: parser OFX + `PesquisarTitulos` + matching com fila de
   exceção + persistência do vínculo `FITID ⇄ baixa`, reaproveitando o padrão de
   chamada genérica de [`../docs-erp-omie/05-exemplos-de-uso.md`](../docs-erp-omie/05-exemplos-de-uso.md).
3. Definir regras de tolerância de matching (data, valor, juros/desconto).
4. Rodar em modo simulação (sem baixar) para validar a taxa de acerto do matching
   antes de executar baixas reais.

---

_Documento de proposta elaborado para documentação interna do projeto de
integração Omie._
