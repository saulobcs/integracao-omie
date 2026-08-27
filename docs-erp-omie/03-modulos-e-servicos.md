# 03 — Catálogo Detalhado de Módulos e Serviços

Detalhamento dos serviços da API Omie por módulo, incluindo **endpoint**,
**métodos (`call`)** e **campos/parâmetros-chave** de cada serviço.

Todas as chamadas seguem o mesmo envelope JSON via **POST**:

```json
{ "call": "<Metodo>", "app_key": "...", "app_secret": "...", "param": [ { ... } ] }
```

Base de URL: `https://app.omie.com.br` + o endpoint indicado. Todos os serviços
estão na versão **v1**.

> **Sobre a confiabilidade dos dados:** endpoints, métodos e campos foram
> confirmados consultando diretamente as páginas de documentação de cada recurso
> (`https://app.omie.com.br/api/v1/<modulo>/<recurso>/`). Onde a página não expôs
> a lista de métodos, aplica-se o padrão de nomenclatura da Omie
> (`Incluir/Alterar/Consultar/Excluir/Listar/Upsert`) — esses casos estão
> sinalizados. Itens marcados como **"não confirmado"** não puderam ser validados
> como serviço de API independente (frequentemente são enums embutidos em outra
> estrutura). Confirme sempre na página oficial antes de implementar.

## Convenções de nomenclatura

| Prefixo | Finalidade |
|---------|-----------|
| `Listar*` / `Pesquisar*` | Listagem em lote paginada |
| `Consultar*` / `Obter*` | Consulta de um único registro |
| `Incluir*` | Criação |
| `Alterar*` | Atualização |
| `Excluir*` | Exclusão |
| `Upsert*` | Inclui ou altera conforme existência (usa código de integração) |

Índice de módulos:

1. [Geral](#1-geral)
2. [CRM](#2-crm)
3. [Finanças](#3-finanças)
4. [Compras, Estoque e Produção](#4-compras-estoque-e-produção)
5. [Vendas e NF-e](#5-vendas-e-nf-e)
6. [Serviços e NFS-e](#6-serviços-e-nfs-e)
7. [Painel do Contador](#7-painel-do-contador)

---

## 1. Geral

> Cadastros compartilhados por todos os módulos, como clientes e fornecedores.

### Clientes / Fornecedores / Transportadoras
- **Endpoint:** `/api/v1/geral/clientes/`
- **Métodos:** `IncluirCliente`, `AlterarCliente`, `ConsultarCliente`, `ExcluirCliente`, `ListarClientes`, `UpsertCliente` (padrão Omie; a página expõe a estrutura `ClientesCadastro`).
- **Campos-chave:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `codigo_cliente_omie` | integer | retorno/chave | Código do cliente/fornecedor no Omie |
| `codigo_cliente_integracao` | string(60) | não | Código de integração com sistema legado |
| `razao_social` | string(60) | **sim** | Razão social |
| `cnpj_cpf` | string(20) | obrig. p/ NF-e/NFS-e | CNPJ / CPF |
| `nome_fantasia` | string(100) | obrig. p/ NF-e/NFS-e | Nome fantasia |
| `email` | string(500) | obrig. p/ NF-e/NFS-e | E-mail |
| `estado` | string(2) | obrig. p/ NF-e/NFS-e | Sigla do estado (via `ListarEstados`) |
| `cidade` | string(40) | não | Código IBGE ou nome (via `PesquisarCidades`) |
| `tipo_atividade` | string(1) | não | Via `ListarTipoAtiv` |
| `cnae` | string(7) | não | CNAE fiscal (via `ListarCNAE`) |
| `tags` | array | não | Tags do cadastro |
| `inativo` | string(1) | não | Cliente inativo (S/N) |

### Clientes - Características
- **Endpoint:** `/api/v1/geral/clientescaract/`
- **Métodos:** `IncluirCaractCliente`, `AlterarCaractCliente`, `ConsultarCaractCliente`, `ExcluirCaractCliente`, `ExcluirTodasCaractCliente`.
- **Campos-chave:** `codigo_cliente_omie` (integer), `codigo_cliente_integracao` (string 60), `campo` (string 30, obrigatório — nome da característica), `conteudo` (string 60, obrigatório na inclusão).

### Tags (de cliente)
- **Endpoint:** `/api/v1/geral/clientetag/` (o `geral/tags` genérico retorna 404)
- **Métodos:** `ExcluirTodas` (confirmado); estruturas de incluir/listar/excluir presentes.
- **Campos-chave:** `nCodCliente` (integer), `cCodIntCliente` (string 60), `tags` (objeto: `tag` text; retorno `nCodTag` integer).

### Projetos
- **Endpoint:** `/api/v1/geral/projetos/`
- **Métodos:** `IncluirProjeto`, `AlterarProjeto`, `ConsultarProjeto`, `ExcluirProjeto`, `ListarProjetos`, `UpsertProjeto`.
- **Campos-chave:** `codigo` (integer), `codInt` (string 20), `nome` (string 70), `inativo` (string 1).

### Cadastros Auxiliares (Geral)

| Serviço | Endpoint | Métodos | Campos-chave |
|---------|----------|---------|--------------|
| Empresas | `/api/v1/geral/empresas/` | Padrão Omie (estrutura `EmpresasCadastro`) | `codigo_empresa`, `cnpj`, `razao_social`, `regime_tributario`, `optante_simples_nacional`, `inativa` |
| Departamentos | `/api/v1/geral/departamentos/` | `IncluirDepartamento`, `AlterarDepartamento`, `ConsultarDepartamento`, `ExcluirDepartamento`, `ListarDepartamentos` | `codigo` (string 40), `descricao` (string 50), `estrutura`, `inativo`, `nivel_totalizador` |
| Categorias | `/api/v1/geral/categorias/` | `IncluirCategoria`, `AlterarCategoria`, `ConsultarCategoria`, `ListarCategorias`, `IncluirGrupoCategoria`, `AlterarGrupoCategoria` | `codigo` (string 20), `descricao`, `natureza`, `tipo_categoria`, `codigo_dre`, `conta_inativa` |
| Parcelas | `/api/v1/geral/parcelas/` | Padrão Omie (estrutura `Parcelas`) | `cParcela` (text — regra, ex. "30/60/90") |
| Tipos de Atividade | `/api/v1/geral/tpativ/` | `ListarTipoAtiv` | `cCodigo` (string 1), `cDescricao` (string 30) |
| CNAE | `/api/v1/produtos/cnae/` | `ListarCNAE` | `nCodigo` (string 7), `cDescricao`, `cEstrutura` |
| Cidades | `/api/v1/geral/cidades/` | `PesquisarCidades` | `filtrar_por_uf`, `filtrar_cidade_contendo`; retorna `nCodIBGE`, `cCod` |
| Países | `/api/v1/geral/paises/` | `ListarPaises` | `cCodigo` (string 4), `cDescricao`, `cCodigoISO` |
| Estados | `/api/v1/geral/estados/` | `ListarEstados` | `cCodigo` (string 2), `cDescricao`, `cSigla` |
| Tipos de Anexos | `/api/v1/geral/tiposanexo/` | `ListarTiposAnexos` | `codigo` (string 10), `descricao` (string 100) |
| Documentos Anexos | `/api/v1/geral/anexo/` | `IncluirAnexo`, `ConsultarAnexo`, `ObterAnexo`, `ListarAnexo`, `ExcluirAnexo` | `cTabela` (cliente/produto/pedido-venda/...), `nId` (obrigatório), `cNomeArquivo`, `cArquivo` (base64), `cMd5` |
| Vendedores | `/api/v1/geral/vendedores/` | `IncluirVendedor`, `AlterarVendedor`, `ConsultarVendedor`, `ExcluirVendedor`, `ListarVendedores`, `UpsertVendedor` | `codigo`, `codInt`, `nome`, `email`, `comissao`, `inativo` |

**Não confirmados como serviço de API dedicado:** Tipo de Entrega, Tipo de
Assinante, Tarefas (do módulo Geral).

---

## 2. CRM

> Contas + Contatos + Oportunidades para fechar mais negócios e vender mais.

### Contas
- **Endpoint:** `/api/v1/crm/contas/`
- **Métodos:** `IncluirConta`, `AlterarConta`, `ConsultarConta`, `ExcluirConta`, `ListarContas`, `UpsertConta`, `VerificarConta`.
- **Campos-chave (blocos):** `identificacao` (`cCodInt`, `cNome` string 100, `cNomeFantasia`, `cDoc` CNPJ/CPF, `nCodVend`, `dDtReg`, `cObs`), `endereco`, `telefone_email` (`cEmail`, `cWebsite`), `informacoesAdicionais` (`nNumFunc`, `cCnae`, `cRegTrib`), `tags`, `caracteristicas`, `contatos`.

### Contatos
- **Endpoint:** `/api/v1/crm/contatos/`
- **Métodos:** `IncluirContato`, `AlterarContato`, `ConsultarContato`, `ExcluirContato`, `ListarContatos`, `UpsertContato`, `VerificarContato`.
- **Campos-chave:** `nCod` (integer), `cCodInt` (text), `cNome` (string 60), `cSobrenome`, `cCargo`, `dDtNasc`, `nCodVend`, `nCodConta`; blocos `endereco` e `telefone_email` (`cEmail`, `cNumCel1`).

### Oportunidades
- **Endpoint:** `/api/v1/crm/oportunidades/`
- **Métodos:** `IncluirOportunidade`, `AlterarOportunidade`, `ConsultarOportunidade`, `ExcluirOportunidade`, `ListarOportunidades`, `UpsertOportunidade`.
- **Campos-chave (blocos):** `identificacao` (`nCodOp`, `cCodIntOp`, `cDesOp` string 100, `nCodConta`, `nCodContato`, `nCodOrigem`, `nCodSolucao`, `nCodVendedor`), `fasesStatus` (`nCodFase`, `nCodStatus`, `nCodMotivo`), `ticket` (`nProdutos`, `nServicos`, `nRecorrencia`, `nTicket`), `previsaoTemp` (`nTemperatura`, `nMesPrev`, `nAnoPrev`), `envolvidos`, `concorrentes` (array), `tarefas` (array).

### Cadastros Auxiliares (CRM)

Todos seguem o mesmo padrão: apenas `ListarX`, request paginado (`pagina`,
`registros_por_pagina`, `ordenar_por`) e retorno com `nCodigo` + descrição.

| Serviço | Endpoint | Método | Campos-chave |
|---------|----------|--------|--------------|
| Soluções | `/api/v1/crm/solucoes/` | `ListarSolucoes` | `nCodigo`, `cDescricao` (string 100), `cInativo` |
| Fases | `/api/v1/crm/fases/` | `ListarFases` | `nCodigo`, `cDescrPadrao`, `cDescrUsuario`, `nOrdem` |
| Status | `/api/v1/crm/status/` | `ListarStatus` | `nCodigo`, `cDescricao` (string 30) |
| Motivos | `/api/v1/crm/motivos/` | `ListarMotivos` | `nCodigo`, `cDescricao` (string 40) |
| Tipos | `/api/v1/crm/tipos/` | `ListarTipos` | `nCodigo`, `cDescricao` (string 30) |
| Parceiros | `/api/v1/crm/parceiros/` | `ListarParceiros` | `nCodigo`, `cDescricao`, `cEmail`, `cInativo` |
| Finders | `/api/v1/crm/finders/` | `ListarFinders` | `nCodigo`, `cNome`, `cEmail`, `cInativo` |
| Origens | `/api/v1/crm/origens/` | `ListarOrigens` | `nCodigo`, `cDescricao`, `cObservacao` |
| Concorrentes | `/api/v1/crm/concorrentes/` | `ListarConcorrentes` | `nCodigo`, `cDescricao` (string 40) |
| Verticais | `/api/v1/crm/verticais/` | `ListarVerticais` | `nCodigo`, `cDescricao` (string 50) |
| Usuários / Vendedores / Pré-Vendas / Telemarketing | `/api/v1/crm/usuarios/` | `ListarUsuarios`, `ObterUsuarios` | `nCodigo`, `cNome`, `cEmail`, `cTelefone`, `nMeta` |

**Observações:** Vendedores, Pré-Vendas e Telemarketing do CRM são cobertos por
`/api/v1/crm/usuarios/`. **Tarefas / Tipos de Tarefas** aparecem embutidas na
estrutura de Oportunidades (bloco `tarefas`); não foi confirmado serviço isolado.

---

## 3. Finanças

> Extrato multi-contas + Contas a Receber + Contas a Pagar + Fluxo de Caixa.

### Contas Correntes (cadastro)
- **Endpoint:** `/api/v1/geral/contacorrente/`
- **Métodos:** `IncluirContaCorrente`, `AlterarContaCorrente`, `ConsultarContaCorrente`, `ExcluirContaCorrente`, `ListarContasCorrentes`, `ListarResumoContasCorrentes`, `UpsertContaCorrente`, `UpsertContaCorrentePorLote`, `PesquisarContaCorrente` (DEPRECATED).
- **Campos-chave:** `nCodCC` (integer), `cCodCCInt` (string 20), `tipo_conta_corrente` (string 2 — CC/CX/CP/CR...), `codigo_banco` (string 3), `descricao` (string 40), `codigo_agencia`, `numero_conta_corrente`, `saldo_inicial`, `inativo`.

### Contas Correntes - Lançamentos
- **Endpoint:** `/api/v1/financas/contacorrentelancamentos/`
- **Métodos:** `IncluirLancCC`, `AlterarLancCC`, `ConsultaLancCC`, `ExcluirLancCC`, `ListarLancCC`.
- **Campos-chave:** `nCodLanc` (integer), `cCodIntLanc` (string 20, obrig. inclusão), `cabecalho.nCodCC` (obrigatório), `cabecalho.dDtLanc`, `cabecalho.nValorLanc`, `detalhes.cCodCateg`, `detalhes.cTipo` (DIN/BOL/TED...), `transferencia.nCodCCDestino`.

### Contas a Pagar - Lançamentos
- **Endpoint:** `/api/v1/financas/contapagar/`
- **Métodos:** `IncluirContaPagar`, `AlterarContaPagar`, `ConsultarContaPagar`, `ExcluirContaPagar`, `ListarContasPagar` (padrão Omie; página expõe estrutura `LancamentoContaPagar` e operações de baixa via bloco `pagamento`).
- **Campos-chave:** `codigo_lancamento_omie` (chave), `codigo_lancamento_integracao` (string 60, obrig. inclusão), `codigo_cliente_fornecedor` (obrigatório), `data_vencimento` (dd/mm/aaaa, obrigatório), `valor_documento` (obrigatório), `codigo_categoria`, `data_previsao` (obrigatório), `id_conta_corrente`, `numero_documento_fiscal`, `id_origem` (APIP/MANP/NFEP...), `baixar_documento` (S/N), `pagamento` (detalhes da baixa).

### Contas a Receber - Lançamentos
- **Endpoint:** `/api/v1/financas/contareceber/`
- **Métodos:** `IncluirContaReceber`, `AlterarContaReceber`, `ConsultarContaReceber`, `ExcluirContaReceber`, `ListarContasReceber`, `UpsertContaReceber`, `IncluirContaReceberPorLote`, `UpsertContaReceberPorLote`, `LancarRecebimento`, `CancelarRecebimento`, `ConciliarRecebimento`, `DesconciliarRecebimento`, `CancelarContaReceber`, `IncluirDistribuicaoDepartamento`, `AlterarDistribuicaoDepartamento`, `ExcluirDistribuicaoDepartamento`.
- **Campos-chave:** `codigo_lancamento_omie` (chave), `codigo_lancamento_integracao` (string 60, obrig. inclusão), `codigo_cliente_fornecedor` (obrigatório), `data_vencimento` (obrigatório), `valor_documento` (obrigatório), `codigo_categoria`, `data_previsao` (obrigatório), `id_conta_corrente`, `baixar_documento` (S/N), `recebimento` (detalhes da baixa), `repeticao`.

### Contas a Receber - Boletos
- **Endpoint:** `/api/v1/financas/contareceberboleto/`
- **Métodos:** `GerarBoleto`, `ObterBoleto`, `CancelarBoleto`, `ProrrogarBoleto`.
- **Campos-chave:** `nCodTitulo` ou `cCodIntTitulo` (informar um dos dois), `dDtVenc` (nova data em ProrrogarBoleto); retorno: `cLinkBoleto`, `cNumBoleto`, `cCodBarras`, `cNumBancario`. *Boletos enviados ao banco podem ser tarifados.*

### Contas a Receber - PIX
- **Endpoint:** `/api/v1/financas/pix/`
- **Métodos:** `GerarPix`, `GerarQrCodePix`, `ObterPix`, `ObterStatusPix`, `ListarPix`, `ListarStatusPix`, `CancelarPix`.
- **Campos-chave:** `cCodIntPix` (obrig. em GerarPix), `nIdPix` (chave), `nCodTitulo`, `vValor` (obrigatório), `nIdConta` (default Omie.CASH), `cUrlNotif` (callback); retorno: `cCopiaCola`, `cUrlPix`, `cStatus` (LIQUIDADO/CANCELADO/REGISTRADO).

### Extrato de Conta Corrente
- **Endpoint:** `/api/v1/financas/extrato/`
- **Métodos:** serviço `ExtratoContaCorrente` (nome do `call` não impresso na página).
- **Campos-chave (resposta):** `nCodCC`, `dPeriodoInicial`, `dPeriodoFinal`, `nSaldoAnterior`, `nSaldoAtual`, `nSaldoConciliado`, `nSaldoDisponivel`, `listaMovimentos` (array com `nValorDocumento`, `cSituacao`).

### Orçamento de Caixa
- **Endpoint:** `/api/v1/financas/caixa/`
- **Métodos:** `ListarOrcamentos`.
- **Campos-chave:** `nAno` (obrigatório), `nMes` (obrigatório); retorno: `cCodCateg`, `cDesCateg`, `nValorPrevisto`, `nValorRealizado`.

### Pesquisar Títulos
- **Endpoint:** `/api/v1/financas/pesquisartitulos/`
- **Métodos:** serviço `PesquisarTitulos` (nome do `call` não impresso na página).
- **Campos-chave (filtros):** `nCodTitulo`, `cCodIntTitulo`, `cCPFCNPJCliente`, `dDtVenc`, `cStatus` (RECEBIDO/LIQUIDADO/EMABERTO/ATRASADO...), `cNatureza` (P/R), `cTipo`, `cOperacao`, `nValorTitulo`, `cChaveNFe`.

### Movimentos Financeiros
- **Endpoint:** `/api/v1/financas/mf/`
- **Métodos:** `ListarMovimentos`.
- **Campos-chave:** `nPagina`, `nRegPorPagina`, `cTpLancamento` (CP/CR/BX/CC...), `cStatus`, `cNatureza` (P/R), `dDtVencDe`/`dDtVencAte`, `dDtPagtoDe`/`dDtPagtoAte`, `nCodCC`; retorno com `detalhes` e `resumo` (nValPago/nValAberto/nValLiquido).

### Resumo (Finanças)
- **Endpoint:** `/api/v1/financas/resumo/`
- **Métodos:** `ObterResumoFinancas`, `ObterListaFinancas`, `ObterListaEmAberto`, `ObterDetalhesLancamento`.
- **Campos-chave:** `dDia`, `cTipo` (P/R), `cCodCateg`, `nIdTitulo`, `lApenasResumo`; retorno com totais de conta corrente, a pagar, a receber e fluxo de caixa.

### Cadastros Auxiliares (Finanças)

| Serviço | Endpoint | Métodos | Campos-chave |
|---------|----------|---------|--------------|
| Bancos | `/api/v1/geral/bancos/` | Listagem (estrutura `fin_banco_cadastro`) | `codigo` (string 3), `nome`, `tipo`, `cod_compen` |
| Tipos de Documento | `/api/v1/geral/tiposdoc/` | `PesquisarTipoDocumento`, `ConsultarTipoDocumento` | `codigo` (string 5), `descricao` |
| Contas do DRE | `/api/v1/geral/dre/` | `ListarCadastroDRE` | `codigoDRE`, `descricaoDRE`, `nivelDRE`, `sinalDRE`, `totalizaDRE` |
| Bandeiras de Cartão | `/api/v1/geral/bandeiracartao/` | `ListarBandeiras` | `cCodigo`, `cDescricao` |

**Não confirmados como serviço dedicado** (são enums embutidos em outras
estruturas): Tipos de Contas Correntes (`tipo_conta_corrente`), Finalidade de
Transferência, Origem dos títulos (`id_origem`).

---

## 4. Compras, Estoque e Produção

> Gerencie suas compras, estoque e ordens de produção.

### Produtos
- **Endpoint:** `/api/v1/geral/produtos/`
- **Métodos:** `IncluirProduto`, `AlterarProduto`, `ConsultarProduto`, `ExcluirProduto`, `ListarProdutos`, `UpsertProduto` (estrutura `ProdutosCadastro`).
- **Campos-chave:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `codigo_produto` | integer | retorno/chave | ID do produto no Omie |
| `codigo_produto_integracao` | string(60) | sim (inclusão) | Código de integração |
| `codigo` | string(60) | não | Código/SKU exibido na tela |
| `descricao` | string(120) | **sim** | Descrição do produto |
| `unidade` | string(6) | **sim** | Código da unidade |
| `ncm` | string(13) | sim (inclusão) | Código NCM |
| `valor_unitario` | decimal | **sim** | Preço unitário de venda |
| `codigo_familia` | integer | não | Código da família |
| `tipoItem` | string(2) | não | Tipo do item p/ SPED |
| `ean` | string(14) | não | Código EAN/GTIN |
| `produto_lote` | string(1) | não | Indica se possui lote (S/N) |

### Produtos - Características
- **Endpoint:** `/api/v1/geral/prodcaract/` (vínculo produto↔característica)
- **Métodos:** `IncluirCaractProduto`, `AlterarCaractProduto`, `ConsultarCaractProduto`, `ExcluirCaractProduto`, `ListarCaractProduto`.
- **Campos-chave:** `nCodProd`/`cCodIntProd`, `nCodCaract`/`cCodIntCaract`, `cConteudo`, `cExibirItemNF`, `cExibirItemPedido`, `cExibirOrdemProd`.
- **Cadastro de características:** `/api/v1/geral/caracteristicas/` — `IncluirCaracteristica`, `AlterarCaracteristica`, `ConsultarCaracteristica`, `ExcluirCaracteristica`, `ListarCaracteristicas` (`cNomeCaract` único, `conteudosPermitidos`).

### Produtos - Estrutura (Malha / BOM)
- **Endpoint:** `/api/v1/geral/malha/`
- **Métodos:** `IncluirEstrutura`, `AlterarEstrutura`, `ConsultarEstrutura`, `ExcluirEstrutura`, `ListarEstruturas`.
- **Campos-chave:** `idProduto`/`intProduto`, `idProdMalha`/`intProdMalha` (produto filho), `quantProdMalha`, `percPerdaProdMalha`, `codigo_local_estoque`; retorno com `custoProducao` (vMOD, vGGF).

### Produtos - Kit
- **Endpoint:** não há serviço dedicado. O KIT é tratado dentro de
  `/api/v1/geral/produtos/` via array `componentes_kit`.

### Produtos - Variação
- **Endpoint:** não confirmado como serviço dedicado. No cadastro de produtos
  existem os campos `produto_variacao`, `variacao`, `id_produto_variacao` (consulta).

### Produtos - Lote
- **Endpoint:** não confirmado como serviço dedicado. Dados de lote aparecem
  embutidos via estrutura `lote_validade` (`nIdLote`, `nQtdLote`, `cNumLote`,
  `dDataFab`, `dDataVal`) em Recebimento NF-e, Nota de Entrada, Ajuste de Estoque e OP.

### Requisições de Compra
- **Endpoint:** `/api/v1/produtos/requisicaocompra/`
- **Métodos:** `IncluirReq`, `AlterarReq`, `ConsultarReq`, `ExcluirReq`, `PesquisarReq`, `UpsertReq`.
- **Campos-chave:** `codReqCompra`, `codIntReqCompra`, `codCateg`, `codProj`, `dtSugestao`, `ItensReqCompra` (array: `codProd`, `qtde`, `precoUnit`).

### Pedidos de Compra
- **Endpoint:** `/api/v1/produtos/pedidocompra/`
- **Métodos:** `IncluirPedCompra`, `AlteraPedCompra`, `ConsultarPedCompra`, `ExcluirPedCompra`, `PesquisarPedCompra`, `UpsertPedCompra`.
- **Campos-chave:** `cabecalho` (`cCodIntPed`, `nCodPed`, `dDtPrevisao`, `nCodFor` fornecedor, `nCodCC`, `cCodCateg`, `nCodCompr` comprador), blocos `produtos_incluir` (`nCodProd`, `nQtde`, `nValUnit`, impostos), `parcelas_incluir`, `frete_incluir`.

### Ordens de Produção
- **Endpoint:** `/api/v1/produtos/op/`
- **Métodos:** `IncluirOrdemProducao`, `AlterarOrdemProducao`, `ConsultarOrdemProducao`, `ExcluirOrdemProducao`, `ListarOrdemProducao`, `ConcluirOrdemProducao`, `ReverterOrdemProducao`, `UpsertOrdemProducao`.
- **Campos-chave:** `identificacao` (`nCodOP`, `cCodIntOP`, `nCodProduto`, `dDtPrevisao`, `nQtde`, `codigo_local_estoque`), `itens[]` (`nIdProdutoMalha`, `cUtilizarDoEstoque`, `lote_validade`), conclusão (`dDtConclusao`, `nQtdeProduzida`).

### Nota de Entrada
- **Endpoint:** `/api/v1/produtos/notaentrada/`
- **Métodos:** `IncluirNotaEnt`, `AlterarNotaEnt`, `ConsultarNotaEnt`, `ExcluirNotaEnt`, `ListarNotaEnt`, `StatusNotaEnt`.
- **Campos-chave:** `cabec` (`nCodNotaEnt`, `cCodIntNotaEnt`, `nCodCli` fornecedor, `dPrevisao`, `cGeraFinanceiro`, `nQtdeParc`), `produtos[]` (`nCodProd`, `nQtde`, `nValUnit`, `cCFOP`, `cNCM`, impostos ICMS/IPI/PIS/COFINS), `infAdic.cCodCateg`.
- **Nota de Entrada - Faturamento:** operações de faturamento tratadas nas
  transições de status (`StatusNotaEnt`).

### Recebimento de Nota Fiscal
- **Endpoint:** `/api/v1/produtos/recebimentonfe/`
- **Métodos:** `ListarRecebimentos`, `ConsultarRecebimento`, `AlterarRecebimento`, `AlterarRecebimentoConcluido`, `AlterarEtapaRecebimento`, `ConcluirRecebimento`, `ReverterRecebimento`, `ExcluirRecebimento`.
- **Campos-chave:** `cabec` (`nIdReceb`, `nIdFornecedor`, `cChaveNfe`, `cEtapa`, `cNumeroNFe`, `nValorNFe`), `itensRecebimento` (produto, quantidade, CFOP, NCM, impostos), `infoAdicionais` (`cCategCompra`, `nIdConta`, `dRegistro`).

### Estoque

| Serviço | Endpoint | Métodos | Campos-chave |
|---------|----------|---------|--------------|
| Ajustes de Estoque | `/api/v1/estoque/ajuste/` | `IncluirAjusteEstoque`, `ExcluirAjusteEstoque`, `AlterarEstoqueMinimo`, `ListarAjusteEstoque` | `id_prod`, `data`, `quan`, `valor`, `tipo` (ENT/SAI/SLD/TRF), `motivo`, `codigo_local_estoque` |
| Consulta Estoque | `/api/v1/estoque/consulta/` | `PosicaoEstoque`, `ListarPosEstoque` | `id_prod`, `data` (obrigatório), `apenas_saldo`; retorno `saldo`, `cmc`, `reservado`, `fisico`, `estoque_minimo` |
| Movimento Estoque | `/api/v1/estoque/consulta/` | `MovimentoEstoque`, `ListarMovimentoEstoque` | `operacao` (00 ajuste, 11 venda, 21 compra, 28 OP...), `qtde`, `valor`, `saldo`, `cmc` |
| Locais de Estoque | `/api/v1/estoque/local/` | `IncluirLocalEstoque`, `AlterarLocalEstoque`, `ListarLocaisEstoque` | `codigo_local_estoque` (ID), `codigo`, `descricao`, `tipo`, `padrao`, `inativo` |
| Resumo do Estoque | — | Coberto por `ListarPosEstoque` | — |

### Cadastros Auxiliares e Impostos (Compras)

| Serviço | Endpoint | Métodos | Campos-chave |
|---------|----------|---------|--------------|
| Famílias de Produto | `/api/v1/geral/familias/` | `IncluirFamilia`, `AlterarFamilia`, `ConsultarFamilia`, `ExcluirFamilia`, `PesquisarFamilias`, `UpsertFamilia` | `codigo`, `codInt`, `nomeFamilia`, `inativo` |
| Unidades | `/api/v1/geral/unidade/` | `ListarUnidades` | `codigo` (string 6), `descricao` |
| NCM | `/api/v1/produtos/ncm/` | `ListarNCM`, `ConsultarNCM` | `cCodigo` (9999.99.99), `cEX`, `cDescricao` |
| CFOP | `/api/v1/produtos/cfop/` | `ListarCFOP` | `nCodigo`, `cDescricao`, `cTipo` (E/S) |
| CNAE | `/api/v1/produtos/cnae/` | `ListarCNAE` | `nCodigo`, `cDescricao`, `cEstrutura` |
| CEST | `/api/v1/produtos/cest/` | `ListarCEST` | `cCodigo` (string 9), `cDescricao` |

**Não confirmados como serviço de API dedicado:** Compradores, Produto x
Fornecedor, Formas de Pagamento (compras), Cenário de Impostos, Resumo de Compras
e as tabelas de CST/CSOSN/Origem/PIS/COFINS/IPI/Tipo de Cálculo (aparecem como
campos dentro de Nota de Entrada / Recebimento NF-e, ex.: `cSitTrib`, `cSitTribSN`,
`cOrigem`, `cSitTribPIS`, `cSitTribCOFINS`, `cSitTribIPI`, `cEnqIPI`).

---

## 5. Vendas e NF-e

> Venda + Faturamento + Emissão de NF-e.

### Pedidos de Venda
- **Endpoint:** `/api/v1/produtos/pedido/`
- **Métodos:** `IncluirPedido`, `AlterarPedidoVenda`, `AlterarPedFaturado`, `ConsultarPedido`, `ListarPedidos`, `ExcluirPedido`, `StatusPedido`, `TrocarEtapaPedido`, `DevolverPedido`, `SimularImpostos`.
- **Campos-chave:** `cabecalho` (`codigo_pedido`, `codigo_pedido_integracao`, `codigo_cliente`, `etapa`, `codigo_cenario_imposto`), `det[]` (itens: `produto`, `quantidade`, `valor_unitario`, impostos), `frete`, `informacoes_adicionais`, `lista_parcelas`.
- **Faturamento** e **Etapas** são tratados por `StatusPedido` / `TrocarEtapaPedido` neste mesmo endpoint.

### Pedidos de Venda - Etapas
- **Endpoint:** `/api/v1/produtos/pedidoetapas/`
- **Métodos:** `ListarEtapasPedido`.

### CT-e / CT-e OS
- **Endpoint:** `/api/v1/produtos/cte/`
- **Métodos:** `ImportarCTe`, `AlterarCte`, `ExcluirCTe`, `CancelarCTe`, `CartaCorrecaoCTe`, `AverbacaoCTe`, `FaturarCTe`, `FaturarLoteCTe`, `ExcluirFaturaCTe`, `StatusFatura`, `ListarNFeTransp`.

### Cupom Fiscal (NFC-e / CF-e SAT)
- **Endpoint:** `/api/v1/produtos/cupomfiscal/`
- **Métodos:** `ListarCupons`, `CancelarCupom`, `ExcluirCupom`, `ExcluirCuponsPorNumero`, `ExcluirLote`, `DevolverCupom`, `CancelarNFCE`, `CancelarSAT`, `ObterProximoLote` (cobre Adicionar/Cancelar/Consultar/Importar).

### NF-e — Emissão / Importação
- **Endpoint:** `/api/v1/produtos/nfe/`
- **Métodos:** `ImportarNFe`, `ImportarCancNFe`, `ExcluirNFe`, `ListarNFe`.

### NF-e — Consultas / Utilitários
- **Endpoint:** `/api/v1/produtos/nfconsultar/`
- **Métodos:** `ConsultarNF`, `ListarNF` (recuperação de XML/DANFE/logotipo via utilitários do mesmo serviço).

### Cadastros Auxiliares (Vendas)

| Serviço | Endpoint | Métodos | Campos-chave |
|---------|----------|---------|--------------|
| Vendedores | `/api/v1/geral/vendedores/` | `IncluirVendedor`, `AlterarVendedor`, `ConsultarVendedor`, `ExcluirVendedor`, `ListarVendedores`, `UpsertVendedor` | `codigo`, `nome`, `comissao` |
| Tabela de Preços | `/api/v1/produtos/tabelaprecos/` | Padrão Omie | preço por produto/tabela |
| Formas de Pagamento | `/api/v1/produtos/formaspagvendas/` | `ListarFormasPagVendas` | forma de pagamento do pedido |
| Meios de Pagamento | `/api/v1/geral/meiospagamento/` | Listagem | parcelas / meios |
| Etapas de Faturamento | `/api/v1/produtos/etapafat/` | Listagem | etapas do faturamento |
| NCM | `/api/v1/produtos/ncm/` | `ListarNCM`, `ConsultarNCM` | `cCodigo`, `cDescricao` |

**Não confirmados como serviço dedicado:** Pedidos de Venda - Resumido, Remessa
de Produtos (e faturamento), Resumo de Vendas, Obter Documentos, Cenário de
Impostos, Origem do Pedido, Motivos de Devolução (referenciado como
`/api/v1/geral/motivodevolucao/`, não validado individualmente), Importar NFC-e /
CF-e SAT como endpoints isolados (cobertos por `cupomfiscal`).

---

## 6. Serviços e NFS-e

> Ordens de Serviço + Contratos + Faturamento + Emissão de NFS-e.

### Serviços (cadastro)
- **Endpoint:** `/api/v1/servicos/servico/`
- **Métodos:** `IncluirCadastroServico`, `AlterarCadastroServico`, `ConsultarCadastroServico`, `ExcluirCadastroServico`, `ListarCadastroServico`, `UpsertCadastroServico`, `AssociarCodIntServico`.

### Ordens de Serviço
- **Endpoint:** `/api/v1/servicos/os/`
- **Métodos:** padrão Omie (`IncluirOS`/`AlterarOS`/`ConsultarOS`/`ListarOS`); a página expõe as estruturas de campos, mas os nomes de `call` não foram impressos literalmente. **Confirmar na página oficial.**
- **Faturamento / Fat. em Lote:** operações de faturamento de OS (endpoints
  específicos de faturamento não confirmados isoladamente nesta coleta).

### Contratos de Serviço
- **Endpoint:** `/api/v1/servicos/contrato/`
- **Métodos:** `IncluirContrato`, `AlterarContrato`, `ConsultarContrato`, `ListarContratos`, `UpsertContrato`, `ExcluirItem`.

### Contratos de Serviço - Faturamento
- **Endpoint:** `/api/v1/servicos/contratofat/`
- **Métodos:** `FaturarContrato`, `ValidarContrato`, `AtivarContrato`, `ReativarContrato`, `SuspenderContrato`, `CancelarContrato`, `ObterContratos` (cobre faturamento individual e em lote).

### NFS-e — Consultas
- **Endpoint:** `/api/v1/servicos/nfse/`
- **Métodos:** `ListarNFSEs`.

### Cadastros Auxiliares (Serviços)

| Serviço | Endpoint | Métodos |
|---------|----------|---------|
| Vendedores | `/api/v1/geral/vendedores/` | (ver módulo Geral) |
| LC 116 | `/api/v1/servicos/lc116/` | Listagem |
| NBS | `/api/v1/servicos/nbs/` | Listagem |
| Tipos de Tributação | `/api/v1/servicos/tipotrib/` | Listagem |
| IBPT | `/api/v1/servicos/ibpt/` | Listagem |
| Classificação do Serviço | `/api/v1/servicos/classificacaoservico/` | Listagem |
| Tipo de utilização | `/api/v1/servicos/tipoutilizacao/` | Listagem |

**Não confirmados como serviço dedicado:** OS - Faturamento / Fat. em Lote
(endpoints isolados), Contratos - Fat. em Lote (coberto por `contratofat`),
Resumo de Serviços, Obter Documentos, Serviços no Município, Formas de Pagamento
e Etapas de Faturamento (do módulo Serviços), Tipo de Faturamento de Contrato.

---

## 7. Painel do Contador

> Integrações que fazem parte do escritório contábil.

### Documentos Fiscais (XMLs)
- **Endpoint:** `/api/v1/contador/xml/`
- **Métodos:** `ListarDocumentos`.
- **Campos-chave:** `nPagina`, `nRegPorPagina`, `cModelo` (55 NF-e, 65 NFC-e, 57 CT-e, 59 CF-e SAT, 99 NFS-e), `cOperacao` (0 entrada / 1 saída), `cAmbiente` (H/P), `dEmiInicial`/`dEmiFinal`, `nChave`; retorno: `cXml`, `cStatus`, `nValor`.

### Resumo (Fechamento Contábil)
- **Endpoint:** `/api/v1/contador/resumo/`
- **Métodos:** `ObterResumoContador`.
- **Campos-chave:** `dDataInicio`, `dDataFim`; retorno: `listaFechamentoContabil` (`cSituacao`, `cAno`, `cMes`, `cLayout`, `cPeriodo`, `dBloqueado`).

---

## Observações finais

- Os nomes de método e endpoints foram confirmados nas páginas oficiais de cada
  recurso. Onde a página não expôs a lista de `call`, aplicou-se o padrão de
  nomenclatura da Omie — esses casos estão sinalizados com "padrão Omie".
- Vários "serviços" listados na página de índice do portal são, na prática,
  **operações dentro de um endpoint** (ex.: faturamento e etapas de pedido em
  `/produtos/pedido/`) ou **enums embutidos** em estruturas maiores (ex.: CST,
  origem de título, tipo de conta corrente). Esses casos estão marcados como
  "não confirmados como serviço dedicado".
- O envelope de requisição, a autenticação e a paginação são comuns a todos os
  serviços — ver [02-autenticacao-e-requisicoes.md](./02-autenticacao-e-requisicoes.md)
  e [04-boas-praticas.md](./04-boas-praticas.md).

_Fonte: páginas de documentação em `https://app.omie.com.br/api/v1/<modulo>/<recurso>/`
e [developer.omie.com.br/service-list](https://developer.omie.com.br/service-list/).
Conteúdo reescrito e reorganizado para documentação interna._
