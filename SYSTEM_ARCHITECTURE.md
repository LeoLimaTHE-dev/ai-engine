# Arquitetura do ambiente completo

Este documento registra a arquitetura atual do ambiente `C:\IA` como um
sistema completo. Ele complementa, sem substituir:

- `PROJECT_STATE.md`, que registra o estado operacional conhecido do projeto
  `ai-engine`;
- `ARCHITECTURE.md`, que descreve tecnicamente os módulos existentes em
  `src/ai_engine`.

O escopo aqui é a relação entre a aplicação interativa, a biblioteca, os
scripts auxiliares e as áreas de entrada, saída, prompts e dados. O documento
não registra conteúdo pessoal, valores de usage, credenciais ou secrets.

## Visão geral

O ambiente está organizado em duas partes executáveis principais:

- `C:\IA\api\application\ia_interativa.py` é a implementação oficial e
  versionada da aplicação/interface principal. Ela recebe comandos do usuário
  e coordena documentos, sessões, preflight, providers, usage e arquivos.
- `C:\IA\0_Scripts\ia_interativa.py` é somente um launcher local fino, sem
  lógica de negócio, que delega à implementação versionada com
  `runpy.run_path()`.
- `C:\IA\api` contém o projeto `ai-engine`, uma biblioteca Python reutilizável
  responsável por leitura de documentos, workflows, conversa, providers,
  respostas estruturadas, actions, exporters, limites e persistência.

Os demais diretórios de `C:\IA` armazenam documentos do usuário, entradas,
saídas, templates e estado operacional, ou reservam espaço para usos futuros.

## Mapa dos diretórios principais

```text
C:\IA
├── 0_Scripts\       launcher local, ferramentas e scripts manuais
├── 1_Projetos\      documentos organizados por projeto ou domínio
├── 2_Entrada\       arquivos selecionados para processamento
├── 3_Saída\         arquivos produzidos pela aplicação e por scripts
├── 4_Prompts\       templates de prompt reutilizáveis
├── 5_Modelos\       área reservada, atualmente vazia
├── 6_Dados\         sessões persistidas e registros de usage
├── 7_Temporario\    estrutura temporária reservada, atualmente vazia
└── api\              engine, aplicação versionada, documentação e testes
```

### `0_Scripts`

Contém o launcher local da interface e executáveis auxiliares. O launcher
`ia_interativa.py` apenas localiza `api\application\ia_interativa.py` em relação
ao próprio arquivo e transfere a execução com `runpy.run_path()`. Ele não
contém menus, configuração operacional ou chamadas de provider.

Os demais scripts são ferramentas, protótipos, testes manuais ou
implementações antigas e ainda não foram todos migrados para a configuração
central de paths.

### `1_Projetos`

Área documental organizada por domínios como projetos pessoais e de trabalho.
Na arquitetura auditada, não existe referência direta a essa pasta no engine
ou na interface principal. Um documento daqui só participa do fluxo se for
fornecido explicitamente como caminho de entrada ou copiado/selecionado por
outro processo externo.

Não é armazenamento interno do engine.

### `2_Entrada`

Área convencional de entrada. Contém exemplos de documentos, planilhas,
imagens e PDFs compatíveis com os readers do engine.

O default atual da aplicação versionada é
`C:\IA\2_Entrada\batch_teste`, mas a interface permite que o usuário informe
outro arquivo ou diretório. O engine recebe um caminho e não depende
diretamente do nome `2_Entrada`.

### `3_Saída`

Destino convencional dos arquivos gerados. A aplicação versionada envia para essa
pasta os outputs descritos por respostas estruturadas. Alguns scripts manuais
usam subdiretórios próprios, como `actions_teste` e `teste_exporters`.

O engine não fixa `3_Saída`: actions e exporters recebem o diretório ou caminho
de destino do chamador. O conhecimento desse diretório pertence atualmente à
camada de aplicação e aos scripts externos.

### `4_Prompts`

Contém templates Markdown reutilizáveis para análise, comparação e resumo. O
módulo `ai_engine.prompts` procura templates nessa pasta por default, e os
workflows podem combiná-los com uma instrução específica do usuário.

A conversa normal da aplicação não seleciona esses templates. Ela usa
a mensagem livre do usuário, o contexto da sessão e as instruções estruturadas
internas do engine. Portanto, `4_Prompts` participa apenas de fluxos que pedem
explicitamente um `prompt_template`, inclusive alguns scripts manuais.

### `5_Modelos`

Área atualmente vazia e sem referências no código auditado. Os modelos de
Gemini, OpenAI e Anthropic usados pelos adapters são serviços remotos
configurados fora dessa pasta; não existem modelos locais integrados ao fluxo
atual.

### `6_Dados`

Armazena estado operacional local:

- `sessions\`: arquivos JSON com nome, provider, caminho de entrada, memória
  resumida, parâmetros de memória, mensagens recentes e mensagens pendentes de
  compactação;
- `usage\`: CSV append-only com telemetria reportada pelos providers.

Sessões não armazenam os documentos originais. Elas persistem `input_path`, e
a interface precisa reler os documentos ao restaurar uma conversa. Se o
caminho deixar de existir, `ia_interativa.py` pede uma nova localização.

### `7_Temporario`

Possui diretórios reservados para bancos, cache, configurações e índices, mas
não contém arquivos e não participa do fluxo auditado.

### `api`

É o repositório do `ai-engine` e da aplicação. `src/ai_engine` contém a
biblioteca reutilizável, `application/ia_interativa.py` contém a implementação
oficial da interface e `tests` contém a suíte offline e os smoke tests reais
separados. Ainda não existe entry point de console empacotado.

## Separação de responsabilidades

| Área | Responsabilidade atual | Localização principal |
|---|---|---|
| Aplicação/interface | Menus, input humano, confirmação, coordenação de sessão, tratamento de erros e escolha de destinos | `api\application\ia_interativa.py` |
| Launcher local | Delega ao arquivo versionado sem lógica de negócio | `0_Scripts\ia_interativa.py` |
| Biblioteca/engine | Modelos documentais, readers, batch, workflows, chat, providers, parsing, actions, exporters e persistência | `api\src\ai_engine` |
| Entrada | Documentos selecionados para processamento | `2_Entrada` ou qualquer caminho fornecido pelo usuário |
| Saída | Resultados gerados e artefatos de testes manuais | `3_Saída` |
| Prompts | Templates editáveis e instruções internas de sistema | `4_Prompts` e módulos de prompt do engine |
| Dados operacionais | Sessões e telemetria de uso | `6_Dados` |
| Dados do usuário | Documentos e materiais organizados por projeto | `1_Projetos` e arquivos fornecidos como entrada |
| Desenvolvimento | Scripts manuais, suíte offline e smoke tests isolados | `0_Scripts\testar_*`, `api\tests` |

## Fluxo completo do sistema

```text
Usuário
  |
  v
0_Scripts\ia_interativa.py (launcher com runpy)
  |
  v
api\application\ia_interativa.py
  |-- escolhe provider e caminho de entrada
  |-- carrega ou restaura uma sessão
  |-- coordena preflight e confirmação humana
  |-- mede usage antes/depois das operações
  |-- coordena compactação explícita da memória
  |
  +--> 2_Entrada ou outro caminho
  |      |
  |      v
  |    ai_engine.workflow/readers
  |      |
  |      v
  |    DocumentContent[]
  |
  v
ai_engine.chat/workflow
  |-- contexto da sessão
  |-- instrução livre
  |-- template opcional de 4_Prompts
  |-- modo individual ou consolidado
  |
  +-- caminho documental/multimodal
  |     workflows/documentos
  |       |
  |       v
  |     ask_document()
  |       |
  |       v
  |     multimodal.py
  |       |
  |       v
  |     adaptador do provider
  |
  +-- caminho textual, por exemplo compactação da memória
        ask_ai()
          |
          v
        router.py
          |
          v
        adaptador do provider
          |
          v
providers: Gemini | OpenAI | Anthropic
  |-- erros dos SDKs -> ProviderError comum
  |-- OpenAI/Anthropic: retry do engine após normalização
  |-- Gemini: retry nativo de interactions
  |                         |
  |                         +--> 6_Dados\usage\api_usage.csv
  v
resposta textual ou StructuredResult
  |                         |
  |                         +--> estado textual da conversa
  |                               |
  |                               v
  |                          6_Dados\sessions\*.json
  |
  +--> mensagem exibida ao usuário
  |
  +--> ai_engine.actions/exporters
          |
          v
        3_Saída\*
```

O caminho textual usado na compactação chama `ask_ai()`, que passa por
`router.py`. O caminho documental usa os workflows estruturados,
`ask_document()` e `multimodal.py`. Em ambos os casos, os adapters de provider
são stateless; a continuidade da conversa existe porque o contexto local é
reconstruído e reenviado.

## Papel atual da aplicação e do launcher

`api\application\ia_interativa.py` é a camada de aplicação. Ela implementa:

- criação, seleção, restauração, salvamento e exclusão de sessões;
- escolha e troca de provider;
- seleção de arquivo ou diretório de entrada;
- recuperação de caminhos de sessão que foram movidos;
- carregamento dos documentos por meio do engine;
- preflight obrigatório antes da requisição principal;
- confirmação separada antes da compactação de memória;
- comandos interativos `sair`, `limpar`, `uso`, `provider` e `salvar`;
- autosave depois de mudanças relevantes e turnos bem-sucedidos;
- apresentação da resposta;
- execução dos arquivos pedidos em respostas estruturadas;
- resumo do consumo registrado em cada operação;
- tratamento humano estruturado de falhas por `format_error_for_user()`, usando
  tipos e metadata comuns sem interpretar `429`, `quota` ou `rate limit` no
  texto da exceção. `details` não é impresso automaticamente.

A interface não implementa readers, adapters de provider ou exporters. Ela os
coordena por meio da API pública raiz de `ai_engine`, usando exclusivamente um
bloco `from ai_engine import (...)`.

`0_Scripts\ia_interativa.py` não implementa nenhuma dessas responsabilidades.
Seu único papel é permitir que o comando histórico continue funcionando:

```powershell
uv run --project C:\IA\api python C:\IA\0_Scripts\ia_interativa.py
```

O launcher não manipula `sys.path`, `PYTHONPATH`, `.venv`, uv ou a instalação
editable. A resolução de `ai_engine` continua sendo responsabilidade do
ambiente do projeto Python.

## Fronteira entre a interface e o engine

A fronteira conceitual atual é:

```text
application\ia_interativa.py
  fornece: decisões do usuário, confirmação, paths e apresentação
  consome:  documentos, sessão, chat, preflight, usage e actions
                         |
                         v
ai_engine
  fornece:  operações reutilizáveis e objetos de domínio
  não deve decidir: menus, confirmação automática, pasta de entrada ou destino
```

A fronteira pública inicial está estabilizada para a aplicação atual.
`application\ia_interativa.py` não depende diretamente de
`ai_engine.actions`, `ai_engine.chat`, `ai_engine.limits`, `ai_engine.paths`,
`ai_engine.usage` ou `ai_engine.workflow`.

Os tipos públicos de domínio/configuração incluem `OperationalPaths`,
`PreflightReport` e `StructuredResult`. O contrato público de falhas inclui
`ProviderError`, `ProviderRateLimitError`, `ProviderTimeoutError`,
`ProviderConnectionError` e `ProviderRequestError`; o parser de Retry-After
permanece interno. As operações públicas adicionais
consumidas pela aplicação são `get_paths()`, `load_documents()`,
`analyze_documents()`, `format_preflight()`, `build_summary_prompt()`,
`summarize_session()`, `execute_structured_result()`, `get_usage_totals()`,
`usage_difference()` e `format_usage_summary()`.

No preflight, o engine calcula e formata o `PreflightReport`. A aplicação
apresenta o relatório e pede autorização ao usuário por meio de
`confirm_preflight_interactively()`. A função histórica
`ai_engine.limits.confirm_preflight()` continua disponível para consumidores
antigos, mas não faz parte de `ai_engine.__all__` nem da API pública raiz.

Testes de contrato verificam os reexports por identidade, preservam os imports
antigos dos módulos de origem e validam importação sem ciclos, sem iniciar a
aplicação e sem chamadas externas. A superfície pode evoluir de forma
compatível; não está declarada como congelada permanentemente.

Os três adapters normalizam erros dos SDKs e preservam a causa original com
`raise ... from exc`. A aplicação não importa exceções de OpenAI, Anthropic,
Gemini ou `_gaos`. Em falha definitiva, `chat()` não adiciona usuário nem
assistente ao histórico; na compactação, a atualização do resumo só ocorre
depois de resposta válida, preservando o estado anterior em falha.

A configuração operacional de robustez é lida dinamicamente do ambiente:
`AI_PROVIDER_TIMEOUT_SECONDS=300`, `AI_PROVIDER_MAX_RETRIES=2`,
`AI_PROVIDER_RETRY_BASE_DELAY_SECONDS=1` e
`AI_PROVIDER_RETRY_MAX_DELAY_SECONDS=10`. OpenAI e Anthropic usam
`max_retries=0` nos SDKs e o helper interno `retry_provider_call()`, totalizando
por padrão no máximo três tentativas. Apenas `retryable=True` autoriza retry;
Retry-After estruturado prevalece, sem parsing de frases textuais.

`log_usage()` permanece depois do sucesso remoto e fora do retry. Falha ao
gravar usage não repete a operação do provider.

O Gemini é a exceção atual: `google-genai 2.18.1` implementa
`interactions.create()` por `_gaos`; timeout chega via `HttpOptions` em
milissegundos, mas os retries nativos não puderam ser zerados por API pública
confiável. Por isso o retry do engine não é conectado ao Gemini. O SDK mantém
seu retry nativo, sem monkeypatch ou alteração de `_gaos`, e os tipos privados
ficam confinados ao adapter/teste Gemini.

## Inventário resumido de `0_Scripts`

### Interface atual

- `ia_interativa.py`: launcher local fino para a aplicação versionada; não
  contém lógica da interface.

### Ferramentas úteis

- `ver_uso_api.py`: visualização manual de usage agrupado por provider. Lê
  diretamente o mesmo CSV usado pelo engine.

### Desenvolvimento e testes manuais

- `testar_actions.py`: workflow estruturado e geração de arquivos;
- `testar_batch.py`: processamento individual/consolidado e template salvo;
- `testar_docx_reader.py`: inspeção do reader DOCX;
- `testar_exporters.py`: geração manual dos formatos suportados;
- `testar_image_reader.py`: inspeção do reader de imagem;
- `testar_multimodal.py`: chamada multimodal real;
- `testar_pdf_reader.py`: inspeção do reader PDF;
- `testar_preflight.py`: relatório e confirmação manual de preflight;
- `testar_reader.py`: dispatch entre formatos;
- `testar_sessao.py`: persistência e restauração manual de sessão;
- `testar_xlsx_reader.py`: inspeção do reader XLSX.

Esses scripts são harnesses manuais. Eles não substituem a suíte padrão de
testes offline do projeto. Alguns fariam chamadas reais ou gravariam arquivos
se fossem executados.

### Legado

- `testar_chat.py`: interface de chat anterior e mais simples, parcialmente
  substituída por `ia_interativa.py`;
- `teste_ia.py`: smoke test antigo de acesso ao Gemini;
- `resumir_docx.py` e `resumir_texto.py`: fluxos diretos de
  reader -> prompt inline -> provider -> DOCX;
- `Criar_relatorio.py`, `Fazer_docx_ai.py` e `Fazer_docx_python.py`: três
  cópias idênticas de um gerador DOCX simples. Apesar do nome,
  `Fazer_docx_ai.py` não chama um provider.

A classificação registra a função aparente atual. Não implica exclusão nem
autoriza mudança nesses arquivos.

## Dependências de paths

### Configuração central do engine

`ai_engine.paths` expõe `OperationalPaths`, uma configuração imutável que
deriva entrada, saída, prompts, modelos, dados, sessions, usage e temporários de
uma única raiz. A precedência é raiz explícita, `IA_ROOT` presente no ambiente
do processo e, por fim, `C:\IA`.

Prompts, sessions e usage consultam essa configuração no momento da chamada
quando não recebem path explícito. Argumentos explícitos continuam
prevalecendo. `ai_engine.paths` não carrega `.env`, cria diretórios ou participa
da resolução/importação do pacote Python.

### Paths da aplicação e scripts

- a aplicação versionada usa uma instância de `OperationalPaths`, deriva
  `input_dir / "batch_teste"`, `output_dir` e `sessions_dir`;
- sem `IA_ROOT`, esses paths continuam sob `C:\IA`;
- os scripts de resumo apontam para arquivos específicos em `2_Entrada` e
  destinos específicos em `3_Saída`;
- os scripts `testar_*` usam fixtures específicas em `2_Entrada` e, quando
  escrevem, subdiretórios de `3_Saída`;
- os três geradores DOCX apontam diretamente para `C:\IA\3_Saída`;
- `ver_uso_api.py` aponta diretamente para o CSV de `6_Dados\usage`;
- sessões persistidas dependem do `input_path` salvo continuar acessível.

Não há dependência de código identificada para `1_Projetos`, `5_Modelos` ou
`7_Temporario`.

## Duplicações e dívidas técnicas principais

### Duplicações

- três scripts são cópias idênticas do mesmo gerador DOCX;
- `testar_batch.py` e `testar_preflight.py` repetem a lista de extensões e a
  coleta já existente em `ai_engine.workflow`;
- `ver_uso_api.py` reimplementa parte da leitura e agregação de usage, embora
  acrescente o agrupamento por provider;
- os scripts de resumo montam manualmente um fluxo já representado pelos
  readers, workflows e exporters do engine;
- `testar_chat.py` sobrepõe parte da responsabilidade da interface principal.

### Dívidas técnicas e acoplamentos

- scripts auxiliares e legados ainda possuem paths absolutos próprios;
- a interface principal concentra menus, coordenação, persistência,
  telemetria, tratamento de erros e actions em um único arquivo;
- vários scripts executam trabalho no topo do módulo e não são componentes
  seguros para importação como biblioteca;
- sessões não têm versionamento de schema e dependem de caminhos externos;
- usage é append-only e não possui locking ou tolerância ampla a CSV inválido;
- o preflight é aproximado e coordenado externamente, não integrado aos
  workflows de alto nível;
- prompts e configurações estão distribuídos entre Markdown, constantes
  Python, variáveis de ambiente e literais nos scripts;
- o modo pelo qual scripts fora de `api` tornam `ai_engine` importável é uma
  dependência operacional que deve permanecer documentada.

Esses itens descrevem o estado existente. Preferências de nomes ou de
organização visual, isoladamente, não são bugs.

## Áreas atualmente fora do fluxo

- `1_Projetos`: repositório documental do usuário, sem integração direta;
- `5_Modelos`: vazio e sem integração com modelos locais;
- `7_Temporario`: diretórios vazios e sem consumidores identificados.

Essas áreas não devem ser movidas ou redefinidas antes de haver um caso de uso
e um contrato explícito com a aplicação.

## Estratégia de evolução segura

Nenhum arquivo precisa ser movido para iniciar a evolução arquitetural. A
ordem segura é:

1. preservar como baseline os 410 testes offline e o comportamento de
   `application\ia_interativa.py`;
2. documentar o comando e o ambiente usados para tornar `ai_engine` importável
   pelos scripts externos;
3. manter a implementação da aplicação versionada junto ao engine e o launcher
   externo sem lógica de negócio;
4. migrar gradualmente ferramentas e scripts legados para `ai_engine.paths`,
   mantendo os mesmos defaults de `C:\IA`;
5. manter compatível a API pública já estabilizada para a aplicação atual e
   expandi-la somente quando houver contrato e testes claros;
6. separar gradualmente as responsabilidades internas da interface, mantendo
   seu ponto de entrada e comportamento observável;
7. permitir configuração compatível de prompts, sessions e usage antes de
   considerar qualquer mudança de diretório;
8. tratar scripts manuais e legados somente depois da estabilização da
   aplicação principal, decidindo quais serão exemplos, ferramentas ou
   artefatos históricos;
9. abordar `1_Projetos`, `5_Modelos` e `7_Temporario` por último, pois não
   participam do fluxo atual;
10. revisar separadamente a política de armazenamento de configurações,
    secrets e dados pessoais, sem incorporar seus valores à documentação.

Continuam como dívidas técnicas prioritárias: eventual revisão do retry Gemini
quando o SDK expuser controle público confiável; configuração uniforme de
`.env`, modelos e parâmetros dos providers; validação mais forte de structured
outputs; versionamento e migração de sessões; documentação de instalação e uso
no `README.md`; e migração dos scripts auxiliares e legados.

Essa sequência mantém a estrutura atual válida enquanto reduz o acoplamento
antes de qualquer movimentação física de arquivos.
