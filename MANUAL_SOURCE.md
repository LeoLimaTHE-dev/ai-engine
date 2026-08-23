# Manual humano do ambiente ai-engine

> Fonte técnica viva para o futuro manual em Word do ambiente local
> multi-provider. Atualize este arquivo quando a operação do sistema mudar.
> Ele não substitui o README, o estado técnico, o handoff para outra IA nem o
> snapshot histórico da v1.

## 1. Finalidade e papel deste documento

O `ai-engine` é um ambiente local em Python para ler arquivos, conversar com
modelos de diferentes providers e gerar resultados em TXT, Markdown, DOCX,
PDF e XLSX. Ele integra OpenAI, Anthropic/Claude e Gemini/Google sem guardar
as credenciais na documentação.

Este manual é voltado à pessoa que usa, mantém ou desenvolve o ambiente. Os
documentos do projeto têm papéis diferentes:

| Documento | Papel |
|---|---|
| `README.md` | Visão rápida para instalação e uso. |
| `PROJECT_STATE.md` | Estado técnico vivo do projeto. |
| `MANUAL_SOURCE.md` | Fonte viva do manual humano. |
| `HANDOFF_V1.md` | Contexto para outra IA continuar o desenvolvimento. |
| `V1_SNAPSHOT.md` | Registro histórico da v1, imutável depois da tag `v1.0.0`. |

`MANUAL_SOURCE.md` é a fonte oficial e viva do manual. O Guia em Word é um
documento derivado para consulta humana, distribuído em `workspace_assets` e
instalado pelo setup em
`<Root>\Guia_Ambiente_IA_Multi_Provider_v1.1.1.docx`. O DOCX deve ser atualizado
conscientemente a partir desta fonte; esta revisão não o modifica.

## 2. Voltei depois de meses — o que faço?

### Quero apenas usar a IA

O caminho recomendado para o uso cotidiano da v1 é o launcher:

```text
C:\IA\Iniciar IA.bat
```

1. abra `C:\IA` no Explorador de Arquivos;
2. dê dois cliques em `Iniciar IA.bat`;
3. aguarde o menu da aplicação;
4. crie uma sessão ou continue uma sessão existente;
5. use a IA normalmente e saia pelo próprio menu.

Não é necessário abrir o VS Code, executar `uv sync` ou rodar os testes toda
vez que quiser apenas usar a aplicação.

### Quero manter, alterar ou testar o sistema

Abra o PowerShell ou o terminal do VS Code e execute, uma linha de cada vez:

```powershell
cd C:\IA\api
git status
uv sync
uv run pytest -q
```

O propósito de cada comando é:

1. entrar no repositório e projeto Python correto;
2. verificar se há mudanças locais antes de trabalhar;
3. sincronizar o ambiente virtual com `pyproject.toml` e `uv.lock`;
4. validar a suíte offline.

Regra de localização:

- `C:\IA` é o workspace operacional;
- `C:\IA\api` é o repositório Git e projeto Python;
- `C:\IA\2_Entrada` recebe arquivos de entrada;
- `C:\IA\3_Saída` recebe arquivos gerados;
- `C:\IA\4_Prompts` contém prompts reutilizáveis;
- `C:\IA\6_Dados\sessions` contém sessões salvas;
- `C:\IA\6_Dados\usage\api_usage.csv` registra usage reportado pelos
  providers.

Não execute comandos Git em `C:\IA` supondo que ele seja o repositório. O
launcher fica no workspace, fora do repositório, e não deve ser movido para
`C:\IA\api`.

## 3. Começo rápido

### 3.0 Instalação nova e reproduzível

Na v1.1.0, primeiro escolha uma raiz operacional. Nos exemplos deste manual ela
é `C:\IA`. O contrato de instalação é sempre:

```text
<Root>\api
```

O repositório deve ser clonado diretamente na subpasta `api`; o setup não move
nem duplica um clone feito em outro lugar. Para uma instalação padrão:

```powershell
git clone https://github.com/LeoLimaTHE-dev/ai-engine.git C:\IA\api
cd C:\IA\api
.\scripts\setup_workspace.ps1
```

O setup:

- cria a estrutura do workspace, sem apagar nem esvaziar pastas existentes;
- copia os quatro prompts oficiais de `workspace_assets`;
- instala o manual humano em
  `<Root>\Guia_Ambiente_IA_Multi_Provider_v1.1.1.docx`;
- gera `<Root>\Iniciar IA.bat` com os paths da instalação;
- cria `<Root>\api\.env` a partir de `.env.example` somente se estiver ausente;
- não lê nem substitui um `.env` existente;
- executa `uv sync` por padrão;
- não toca em entradas, saídas, sessões, usage ou prompts personalizados;
- não chama providers nem valida API keys.

Para instalar em outra raiz, o clone também precisa respeitar o contrato. Por
exemplo, para `D:\IA`:

```powershell
git clone https://github.com/LeoLimaTHE-dev/ai-engine.git D:\IA\api
cd D:\IA\api
.\scripts\setup_workspace.ps1 -Root "D:\IA"
```

Não clone em `C:\IA\api` e passe `-Root "D:\IA"`: nessa situação o setup
interrompe com erro e não move o repositório.

Parâmetros disponíveis:

| Parâmetro | Uso |
|---|---|
| `-Root "D:\IA"` | Declara a raiz operacional; o repo precisa estar em `D:\IA\api`. |
| `-SkipSync` | Cria a estrutura e instala assets sem executar `uv sync`. |
| `-Force` | Substitui somente launcher, prompts oficiais e manual oficial conflitantes. |

Use `-Force` apenas depois de comparar o arquivo local com o asset oficial. A
opção não substitui `.env`, não apaga prompts personalizados ou outros DOCX e
não toca em dados do usuário. Consulte `SETUP_WORKSPACE.md` para o procedimento
completo.

### 3.1 Requisitos

- Windows com PowerShell;
- `uv` instalado;
- Git para clonar o repositório;
- rede para o clone e para `uv sync`, salvo preparação com `-SkipSync`;
- uma API key válida para cada provider que a pessoa realmente pretenda usar.

O projeto requer Python 3.14 ou mais recente. O `uv` pode localizar ou
provisionar a versão apropriada durante o sync; não é necessário ativar uma
`.venv` manualmente.

Para preparar ou atualizar as dependências:

```powershell
cd C:\IA\api
uv sync
```

### 3.2 Configurar o `.env`

Em uma instalação nova, o setup cria `<Root>\api\.env` a partir de
`.env.example`. Abra o arquivo criado e preencha somente as credenciais dos
providers que pretende usar. Exemplo sem valores reais:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...

OPENAI_MODEL=...
ANTHROPIC_MODEL=...
GEMINI_MODEL=...
```

Não é necessário configurar os três providers. Um provider sem credencial não
pode ser chamado, mas os demais continuam disponíveis. O `.env` não deve ser
commitado, enviado a outra pessoa nem copiado para documentos. O engine carrega
esse arquivo a partir da raiz do projeto.

### 3.3 Iniciar a aplicação pelo launcher — recomendado

Para uso cotidiano, abra `<Root>` no Explorador de Arquivos e dê dois cliques
em:

```text
<Root>\Iniciar IA.bat
```

O launcher:

- entra em `<Root>\api`;
- define `IA_ROOT` como `<Root>` para o processo;
- executa `uv run python application\ia_interativa.py`;
- não exige ativação manual da `.venv`;
- não abre o VS Code;
- não executa testes nem `uv sync`;
- não executa nem altera Git;
- não configura API keys ou modelos;
- deixa a aplicação carregar normalmente a configuração do projeto e do
  `.env`.

Se ocorrer erro ao acessar o projeto ou durante a execução, a janela permanece
aberta com uma mensagem e `pause`, para que o usuário consiga ler o problema.
Em encerramento normal, a janela pode fechar.

O launcher foi validado manualmente na v1 no seguinte escopo:

```text
duplo clique -> menu da aplicação -> saída normal pelo menu
```

Esse smoke não fez chamada a provider.

### 3.4 Primeiro uso depois da instalação

1. preencha suas próprias credenciais em `<Root>\api\.env`;
2. abra `<Root>\Iniciar IA.bat`;
3. escolha **Nova sessão** ou **Continuar sessão**;
4. em uma sessão nova, escolha o provider que possui credencial configurada;
5. escolha um template ou `[0] Nenhum — conversa normal`;
6. indique um arquivo ou uma pasta de `<Root>\2_Entrada`, ou pressione Enter
   para usar a pasta padrão;
7. converse normalmente, confirme o preflight quando quiser realizar a
   chamada e consulte os resultados em `<Root>\3_Saída`;
8. digite `sair` no chat para salvar e encerrar normalmente.

Nenhum é o padrão, inclusive ao pressionar Enter. Se não souber qual template
usar, escolha Nenhum. Templates servem para instruções estáveis que se repetem
em tarefas diferentes; eles não são necessários para liberar capacidades da
IA.

Arquivo ou pasta é opcional para tarefas puramente textuais. Se a pasta padrão
estiver vazia ou contiver apenas formatos não suportados, a aplicação informa
que nenhum documento foi carregado e continua com o chat. Templates para
Cineclube, revisão de texto, brainstorming e tarefas semelhantes não precisam
de um `contexto.txt` artificial.

Esse suporte foi adicionado na v1.1.1. A interface ativa explicitamente
`allow_empty`; a coleta programática continua estrita por padrão.

Uma pasta vazia informada explicitamente tem o mesmo comportamento. Um caminho
inexistente ou um arquivo explicitamente não suportado continua produzindo erro
apropriado; esses casos não são convertidos silenciosamente em uma sessão
vazia.

### 3.5 Iniciar manualmente — troubleshooting e desenvolvimento

Se precisar diagnosticar a inicialização ou estiver desenvolvendo, use:

```powershell
cd C:\IA\api
uv run python application\ia_interativa.py
```

A aplicação apresenta um menu para:

1. criar uma nova sessão;
2. continuar uma sessão existente;
3. listar sessões;
4. excluir uma sessão;
5. sair.

Ao criar uma sessão, informe um nome e siga o fluxo:

```text
provider -> template opcional -> arquivo ou pasta -> chat
```

No menu de templates, Enter ou `0` seleciona
`[0] Nenhum — conversa normal`. Se não souber qual template usar, escolha
Nenhum. Pressionar Enter no campo de entrada usa o default
`C:\IA\2_Entrada\batch_teste`.

Ao continuar uma sessão, os documentos são relidos do caminho salvo. Se esse
caminho não existir mais, a aplicação solicita a nova localização.

Os arquivos gerados são gravados, por padrão, em `C:\IA\3_Saída`. A raiz
operacional pode ser alterada com `IA_ROOT`, mas isso também muda os caminhos
derivados de entrada, saída, prompts, dados e temporários.

O launcher gerado pelo setup já define `IA_ROOT` automaticamente. No uso
cotidiano não é necessário criar essa variável manualmente. Ela controla
entrada, saída, prompts, dados e temporários; o repositório permanece em
`<Root>\api`.

## 4. Uso normal da aplicação

> **Quero apenas usar a IA:** dê dois cliques em
> `C:\IA\Iniciar IA.bat`.
>
> **Quero alterar, desenvolver ou testar o sistema:** abra o VS Code ou o
> PowerShell e trabalhe dentro de `C:\IA\api`.

### 4.1 Fluxo de uma conversa

Depois de abrir ou criar uma sessão:

1. digite a solicitação;
2. responda se espera arquivos nesta resposta;
3. revise o preflight local;
4. confirme ou cancele a chamada;
5. leia a resposta e confira os arquivos criados;
6. consulte o consumo do turno apresentado pela aplicação.

O template é escolhido somente durante a criação e permanece associado à
sessão. Não existe comando para trocá-lo durante o chat na v1. Ao continuar uma
sessão, a aplicação mostra seu nome sem perguntar novamente.

Se a pergunta **“Espera arquivos nesta resposta?”** receber `s`, `sim`, `y`
ou `yes`, o engine usa `expect_outputs=True` e exige uma resposta estruturada
válida. Qualquer outra resposta mantém o modo textual compatível.

### 4.2 Comandos durante o chat

| Comando | Efeito |
|---|---|
| `sair` | Salva a sessão e encerra o chat. |
| `limpar` | Apaga histórico recente, pendências e resumo da conversa. |
| `uso` | Mostra o usage total registrado localmente. |
| `provider` | Troca o provider; permite manter ou apagar o histórico. |
| `salvar` | Salva a sessão imediatamente. |
| `multiline` ou `multi` | Abre entrada de várias linhas. |

Os comandos digitados dentro do modo multiline são tratados como conteúdo da
mensagem, e não como comandos da aplicação.

### 4.3 Mensagens com várias linhas

No prompt `Você:`, digite:

```text
multiline
```

Cole ou escreva quantas linhas quiser. Encerre com uma linha contendo somente:

```text
/fim
```

O terminador `/fim` não faz parte da mensagem enviada. Se não houver conteúdo
antes dele, nenhuma mensagem é enviada.

### 4.4 Troca de provider

Digite `provider`, escolha o novo provider e decida se deseja manter o
histórico. Os documentos carregados permanecem na sessão. Se o histórico for
apagado, o resumo e as pendências também são limpos.

### 4.5 Autosave e contexto

A sessão é salva na criação, nas mudanças importantes e depois de cada turno
bem-sucedido. Uma resposta estruturada inválida ou uma falha do provider não
adiciona a mensagem ao histórico.

O contexto combina resumo anterior, mensagens recentes, solicitação atual e
documentos. Quando mensagens antigas suficientes aguardam compactação, a CLI
explica que haverá uma chamada adicional, executa um preflight separado e
pede confirmação antes de resumir a memória.

## 5. Geração de arquivos

O contrato de saída aceita `txt`, `md`, `docx`, `pdf` e `xlsx`. O engine valida
todos os pedidos e planeja filenames, extensões, colisões e sheets antes da
primeira escrita.

### 5.1 TXT

- Suporta texto simples em UTF-8.
- É apropriado para conteúdo portátil, logs, listas e integração simples.
- Não preserva formatação rica.

### 5.2 Markdown (`.md`)

- Salva o conteúdo textual em UTF-8.
- É apropriado para documentação e texto com marcação Markdown.
- O exporter não transforma Markdown em layout visual; ele preserva o texto.

### 5.3 DOCX

- Suporta um título opcional e o conteúdo como texto.
- É apropriado quando o resultado precisa ser aberto e editado no Word.
- Na v1 não há tabelas estruturadas, imagens inseridas automaticamente nem
  renderização Markdown avançada.
- O conteúdo é adicionado como um parágrafo textual, não como um modelo rico
  de seções e estilos.

### 5.4 PDF

- Suporta um título opcional e parágrafos de texto em página A4.
- É apropriado para distribuição de um documento textual estável.
- Na v1 não há tabelas estruturadas, imagens inseridas automaticamente nem
  renderização Markdown avançada.
- Texto recebido não é interpretado como markup do ReportLab.

### 5.5 XLSX linear

- Usado quando um output XLSX contém texto, mas nenhuma `ResultTable`.
- Cria a sheet `Resultado`, com título na primeira linha e o conteúdo dividido
  em linhas na coluna A.
- É útil para listas ou conteúdo predominantemente textual em planilha.

### 5.6 XLSX tabular

- Usado quando o output XLSX contém tabelas estruturadas.
- Cria uma sheet por tabela, com headers opcionais e rows.
- Nomes de sheets são normalizados, limitados e desambiguados no planning.
- É o formato estruturado da v1 para dados tabulares. Para tabelas reais,
  prefira XLSX a DOCX ou PDF.

## 6. Trabalhando com imagens

O engine aceita imagens independentes e imagens encontradas dentro de DOCX ou
PDF. Os bytes visuais não são convertidos em texto: são enviados pelos
adapters multimodais, acompanhados de identidade textual.

### 6.1 Imagens externas

Uma imagem fornecida como arquivo independente mantém o filename original,
incluindo espaços, maiúsculas e extensão. Quando ela for relevante para um
documento, a referência manual recomendada é:

```text
[INSERIR IMAGEM: filename]
Legenda sugerida: Figura X – descrição objetiva.
```

Exemplo genérico:

```text
[INSERIR IMAGEM: Foto Principal.jpeg]
```

Não renomeie a imagem, não troque a extensão e não substitua o nome externo
por identificadores internos.

### 6.2 Imagens internas de DOCX ou PDF

Imagens embutidas permanecem vinculadas ao documento de origem. Use:

```text
[INSERIR IMAGEM DO DOCUMENTO: documento | localização | descrição]
Legenda sugerida: Figura X – descrição objetiva.
```

A localização pode ser uma página, posição, seção, tabela ou anexo quando essa
informação estiver disponível. Não apresente uma imagem interna como se fosse
um arquivo independente acessível ao usuário.

### 6.3 Seleção semântica

O modelo pode analisar todas as imagens disponíveis, selecionar somente as
pertinentes, ignorar imagens irrelevantes e associar cada uma à seção adequada.
Não é necessário usar todas as imagens nem repetir a mesma imagem sem motivo.

A v1 produz apenas os marcadores. Ela **não insere fisicamente imagens** em
DOCX ou PDF.

### 6.4 Cautela técnica

Fotografia é evidência visual, não prova automática de uma propriedade que não
possa ser observada. Uma imagem isolada não comprova, por exemplo:

- conformidade normativa completa;
- dimensão exata sem escala ou medição;
- continuidade elétrica ou resistência de isolamento;
- capacidade elétrica;
- torque aplicado;
- aterramento efetivo;
- condição interna ou integridade funcional não visível.

Quando só houver evidência visual, prefira expressões como “visualmente
observado”, “a imagem indica”, “aparentemente”, “é possível observar” e
“requer confirmação em campo, por medição, ensaio ou documentação”. Fatos
explicitamente comprovados nos documentos não devem ser enfraquecidos. Se
texto e fotografia divergirem, registre a divergência.

### 6.5 Template multimodal

O template oficial está em:

```text
C:\IA\4_Prompts\relatorio_multimodal_com_imagens.md
```

Ele reúne as regras de referência manual, seleção semântica, rastreabilidade e
cautela técnica. Seu uso é opt-in; ele não é acrescentado automaticamente a
todas as solicitações.

## 7. Prompts externos

`C:\IA\4_Prompts` é uma biblioteca opcional de instruções reutilizáveis. Crie
um template quando perceber que instruções estáveis estão sendo repetidas em
tarefas diferentes, não apenas porque uma tarefa é possível. Antes de criar
outro arquivo, verifique se um template existente já cobre a necessidade.

Os oficiais são:

| Template | Uso geral |
|---|---|
| `resumir.md` | Produz uma síntese objetiva, preservando os fatos relevantes. |
| `analisar_documentos.md` | Correlaciona arquivos e identifica fatos, divergências, lacunas e pontos relevantes. |
| `comparar_arquivos.md` | Compara informações equivalentes e destaca convergências, divergências e ausências. |
| `relatorio_multimodal_com_imagens.md` | Produz relatório e referencia imagens relevantes para inserção manual. |

Templates destinados ao menu começam com:

```text
# Nome humano
> Descrição: descrição curta
```

`load_prompt()` aceita um nome sem extensão, um filename `.md` ou `.txt`, ou
um caminho completo. Sem diretório explícito, procura na pasta operacional de
prompts. O workflow pode combinar o template carregado com a instrução
específica do usuário. A metadata de apresentação é removida antes do envio ao
modelo.

`discover_prompt_templates()` inclui no menu somente `.md`/`.txt` com metadata
válida. Arquivos experimentais sem metadata continuam carregáveis
explicitamente, mas não aparecem. Nenhum é sempre o default; não há seleção
automática baseada na pergunta.

## 8. Providers e modelos

| Provider | Alias | API usada | Variável de modelo | Modelo native comprovado |
|---|---|---|---|---|
| OpenAI | `openai` | Responses API | `OPENAI_MODEL` | `gpt-5` |
| Anthropic | `anthropic`, `claude` | Messages API | `ANTHROPIC_MODEL` | `claude-sonnet-5` |
| Gemini | `gemini`, `google` | Interactions API | `GEMINI_MODEL` | `gemini-3.5-flash` |

Os nomes de modelo são lidos dinamicamente do ambiente a cada operação. Os
modelos da última coluna são os que possuem evidência local de smoke native
structured na v1; eles não são uma lista de todos os modelos possíveis nem
uma obrigação permanente.

Para `expect_outputs=True`, a decisão considera o provider normalizado e o
modelo documental efetivamente configurado:

- combinação comprovada (`supported`): usa structured output nativo antes da
  chamada;
- modelo não comprovado (`unknown`): usa prompt estruturado legado antes da
  chamada e mantém o parser forte;
- `unknown` não significa necessariamente incompatível.

Depois que uma chamada native começa, não existe uma segunda chamada
automática em modo legado. Refusal, resposta incompleta, rejeição do schema,
quota e demais `ProviderError` são propagados. Isso evita custo e geração
duplicados.

Os adapters consultam defaults próprios quando a variável não está definida.
Como defaults e modelos disponíveis podem evoluir, consulte o código e o
`PROJECT_STATE.md` antes de assumir que o default atual possui capability
native comprovada.

## 9. `.env` e variáveis temporárias

### 9.1 Configuração persistente no projeto

Exemplo seguro de `C:\IA\api\.env`:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...

OPENAI_MODEL=...
ANTHROPIC_MODEL=...
GEMINI_MODEL=...
```

O `.env` persiste entre reinicializações do terminal e é carregado pelo
projeto. Não use esse arquivo como documentação e nunca versione credenciais.

### 9.2 Configuração temporária no PowerShell

Para trocar o Gemini apenas na sessão atual do PowerShell:

```powershell
$env:GEMINI_MODEL="gemini-3.5-flash"
```

O PowerShell **não imprime nada quando essa atribuição funciona**. Para
consultar o valor vigente:

```powershell
$env:GEMINI_MODEL
```

O mesmo padrão vale para `OPENAI_MODEL` e `ANTHROPIC_MODEL`. Uma variável
`$env:...` vale para a sessão atual e os processos iniciados por ela; ao fechar
o terminal, ela normalmente desaparece. Uma variável do processo tem
precedência sobre o valor carregado do `.env`.

## 10. Estrutura de diretórios

Árvore operacional observada em `C:\IA`:

```text
C:\IA
├── 0_Scripts       # launchers e utilitários locais existentes
├── 1_Projetos      # área reservada para projetos do usuário
├── 2_Entrada       # arquivos de entrada
├── 3_Saída         # resultados gerados
├── 4_Prompts       # templates externos reutilizáveis
├── 5_Modelos       # área reservada para modelos/artefatos locais
├── 6_Dados         # sessões e usage persistidos
│   ├── sessions
│   └── usage
├── 7_Temporario    # arquivos temporários operacionais
└── api             # repositório Git e projeto Python
```

Em outra instalação, substitua `C:\IA` por `<Root>`. Os papéis operacionais
permanecem os mesmos:

| Caminho | Finalidade |
|---|---|
| `<Root>\2_Entrada` | Arquivos que serão lidos e analisados. |
| `<Root>\3_Saída` | Resultados gerados pelo engine. |
| `<Root>\4_Prompts` | Templates externos, oficiais ou personalizados. |
| `<Root>\6_Dados\sessions` | Sessões locais persistidas. |
| `<Root>\6_Dados\usage` | Registro local de uso reportado pelos providers. |
| `<Root>\7_Temporario` | Arquivos temporários operacionais. |
| `<Root>\api` | Clone do repositório e projeto Python. |

As pastas `1_Projetos` e `5_Modelos` pertencem à organização do workspace,
mas não se deve presumir uma integração automática com o engine. O cache
`.pytest_cache` pode aparecer durante testes e não é uma pasta operacional do
usuário.

Os assets operacionais da v1 possuem uma cópia versionada em
`C:\IA\api\workspace_assets`. Essa pasta serve somente para representar a
release e reconstruir o workspace: o uso cotidiano continua em
`C:\IA\Iniciar IA.bat` e `C:\IA\4_Prompts`. O engine não lê templates do
snapshot automaticamente.

O repositório contém principalmente:

```text
C:\IA\api
├── application\ia_interativa.py
├── src\ai_engine
│   ├── readers
│   ├── providers
│   └── exporters
├── tests
├── pyproject.toml
└── uv.lock
```

## 11. Arquitetura resumida

O fluxo principal pode ser lido assim:

```text
arquivos
  -> readers
  -> DocumentContent
  -> batch / multimodal
  -> adapter do provider
  -> resposta textual str
  -> parse_structured_result()
  -> validation
  -> planning
  -> actions / exporters
  -> arquivos em C:\IA\3_Saída
```

- **Readers** convertem formatos diferentes para uma representação comum.
- **DocumentContent** reúne origem, texto, tabelas, imagens e metadados.
- **Batch** processa documentos individualmente ou os combina.
- **Multimodal** encaminha texto e imagens ao SDK adequado.
- **Providers** isolam as APIs e normalizam erros e usage.
- **Parser** converte a resposta textual para o domínio estruturado.
- **Validation** verifica contrato e regras semânticas.
- **Planning** determina destinos, extensões, colisões e nomes de sheets.
- **Actions/exporters** gravam os formatos finais.

Essas camadas devem permanecer separadas: uma resposta JSON correta no
transporte ainda pode violar uma regra local ou solicitar um filename inseguro.

## 12. Structured output

Structured output é o contrato usado quando a resposta deve descrever arquivos
a criar. O schema canônico vive em:

```text
src\ai_engine\structured_schema.py
```

`get_structured_result_json_schema()` devolve uma cópia independente do schema
para os adapters. O contrato representa:

- `StructuredResult`: `message` e `outputs`;
- `OutputRequest`: `format`, `filename`, `title`, `content` e `tables`;
- `ResultTable`: `name`, `headers` e `rows`.

Os objetos não aceitam propriedades extras no schema; `title` e `content`
podem ser string ou `null`; os formatos são `txt`, `md`, `docx`, `pdf` e
`xlsx`.

Quando `expect_outputs=True`:

```text
provider + modelo
  -> capability supported: envelope native structured
  -> capability unknown: instruções estruturadas legadas
  -> resposta str
  -> parser forte obrigatório
  -> validation
  -> planning
  -> escrita
```

O schema não representa todas as regras. Segurança de filename, coerência de
extensão, tabelas somente em XLSX, largura das rows, colisões, overwrite e
nomes de sheets continuam locais. Por isso parser, validation e planning não
foram removidos com a adoção do transporte native.

As `STRUCTURED_OUTPUT_INSTRUCTIONS` também permanecem no prompt native da v1,
pois carregam regras semânticas não expressas pelo schema. Uma possível
redução é tema de v2.

## 13. Readers

| Tipo | Extensões | Comportamento principal |
|---|---|---|
| Texto | `.txt` | Lê texto UTF-8. |
| Markdown | `.md`, `.markdown` | Lê UTF-8 bruto; não renderiza Markdown. |
| CSV | `.csv` | Produz uma tabela; aceita UTF-8 com BOM e tenta detectar o dialeto. |
| Word | `.docx` | Extrai parágrafos, tabelas e imagens sob `word/media/`. |
| PDF | `.pdf` | Extrai texto e imagens; renderiza páginas com pouco texto em PNG; não faz OCR local. |
| Excel | `.xlsx`, `.xlsm` | Produz uma tabela por worksheet usando valores calculados. |
| Imagem | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`, `.tiff`, `.tif` | Produz uma imagem com bytes, MIME e filename original. |

O coletor aceita um arquivo ou os filhos diretos de uma pasta. Ele não percorre
subpastas recursivamente. Arquivos suportados são ordenados antes da leitura.

No PDF, páginas com menos de 30 caracteres extraídos podem ser renderizadas a
150 dpi. O reader classifica o documento como `empty`, `digital`, `scanned` ou
`mixed`, mas não executa OCR local.

## 14. Batch e multimodal

> **Uso cotidiano:** ao utilizar `Iniciar IA.bat`, você não precisa selecionar
> manualmente os modos `individual`, `consolidated` ou `auto`. Esses modos fazem
> parte do funcionamento interno do engine. No fluxo padrão, o sistema prepara
> os documentos conforme as regras do modo configurado, enquanto o modelo
> interpreta sua solicitação no chat e decide como analisar, comparar ou
> sintetizar as informações recebidas. Esta seção é principalmente uma
> referência para manutenção, desenvolvimento e criação de scripts.

Há três modos conceituais:

| Modo | Comportamento |
|---|---|
| `individual` | Envia cada documento separadamente. |
| `consolidated` | Combina documentos em um documento virtual e faz uma análise conjunta. |
| `auto` | Um documento vira individual; dois ou mais viram consolidated. |

No modo consolidado, o texto identifica o documento de origem, tabelas recebem
origem e imagens internas são distinguidas. Imagens externas independentes
preservam seu filename. No modo individual múltiplo, cada resposta é associada
ao filename correspondente.

`DocumentContent` pode transportar simultaneamente texto, tabelas e imagens.
Antes do envio visual, imagens são normalizadas para formatos aceitos pelos
providers, sem alterar o arquivo original no disco. Cada adapter acrescenta
metadado textual adjacente para associar a imagem à sua identidade.

## 15. Sessões, contexto, preflight e usage

### 15.1 Sessões e contexto

Sessões são JSON locais em `C:\IA\6_Dados\sessions`. Elas guardam nome,
provider, `prompt_template`, caminho de entrada, resumo, mensagens recentes e
mensagens pendentes de compactação. Somente o filename do template é
persistido; conteúdo e caminho absoluto não são salvos. Os documentos não são
serializados integralmente e são relidos ao restaurar.

Sessões antigas sem `prompt_template` continuam normalmente com `None`. Se o
arquivo persistido desaparecer ou deixar de ter metadata válida, a restauração
avisa, muda a sessão para Nenhum e salva a correção para não repetir o aviso.

Por padrão, a memória mantém até 10 mensagens recentes. Mensagens antigas são
movidas para uma fila e, a partir de 4 pendentes, a aplicação propõe uma
compactação por IA. Esses valores pertencem à sessão e podem evoluir.

### 15.2 Preflight

Antes de cada chamada principal, o preflight estima caracteres, tokens de
texto, quantidade e volume de imagens e número de arquivos. Ele é uma
estimativa local, não a fatura real.

Quando há template, suas instruções efetivas entram na estimativa. A chamada
interna de compactação de memória não recebe o template da sessão.

- situação normal ou warning: confirmação com `s`, `sim`, `y` ou `yes`;
- limites máximos excedidos: confirmação explícita com `CONFIRMAR`.

Cancelar o preflight impede a chamada. Os limites podem ser configurados por
variáveis `AI_WARN_*` e `AI_MAX_*`; consulte `src\ai_engine\limits.py` antes de
alterá-los.

### 15.3 Usage

O usage reportado pelos SDKs é anexado a:

```text
C:\IA\6_Dados\usage\api_usage.csv
```

A CLI mostra a diferença de consumo do turno e o comando `uso` mostra os
totais locais. O registro pode incluir input, output, thinking e cached tokens,
dependendo do provider. Ele não substitui o painel oficial de cobrança.

## 16. Testes

Execute a suíte padrão com:

```powershell
cd C:\IA\api
uv run pytest -q
```

Baseline verificado para esta fonte em 23/08/2026:

```text
876 passed
0 failed
1 warning
```

O warning conhecido é um `DeprecationWarning` interno de `google-genai` sobre
`_UnionGenericAlias`. Ele não representa falha da suíte.

`pyproject.toml` coleta por padrão somente arquivos `test_*_offline.py`. Esses
testes usam mocks, fakes e fixtures locais e não devem chamar providers reais.

Os scripts em `tests\smoke` são verificações manuais separadas. Eles exigem
credenciais, podem consumir quota e **não devem ser executados sem pedido
explícito**. Os smokes native structured registrados para OpenAI `gpt-5`,
Anthropic `claude-sonnet-5` e Gemini `gemini-3.5-flash` passaram em dois casos:
`outputs=[]` e geração TXT end-to-end. Testes manuais anteriores também
validaram TXT, MD, XLSX linear, XLSX tabular, DOCX e PDF; isso não significa
que todos os formatos foram testados em todos os providers.

Smokes manuais adicionais da integração de templates:

- sem provider: `Iniciar IA.bat` -> criar sessão -> selecionar Resumir -> sair
  -> reabrir -> continuar -> `Template da sessão: Resumir`: PASS;
- real: OpenAI + Resumir + pergunta `O que tem aqui?`: resposta em forma de
  síntese, com fatos preservados, em uma chamada de API: PASS.

## 17. Git e manutenção

| Comando | O que faz |
|---|---|
| `cd C:\IA\api` | Entra no repositório correto. |
| `git status` | Mostra branch, arquivos modificados e estado geral. |
| `git status --short` | Mostra uma lista compacta das mudanças. Sem saída significa estado limpo. |
| `git log -5 --oneline` | Mostra os cinco commits mais recentes. |
| `git diff --check` | Procura problemas de whitespace nas mudanças rastreadas. |
| `git diff --stat` | Resume arquivos rastreados alterados; não inclui untracked. |
| `uv sync` | Sincroniza o ambiente virtual e as dependências. |
| `uv run pytest -q` | Executa a regressão offline padrão. |

Antes de editar código, confirme o status e leia os módulos e testes
relacionados. Depois, rode testes focais, suíte completa, `git diff --check` e
`git status --short`. Não faça commit antes de revisar o diff e o resultado dos
testes.

### 17.1 Atualização e reinstalação segura

`scripts\setup_workspace.ps1` é idempotente e pode ser executado novamente
depois de atualizar o repositório. Ele:

- cria somente diretórios ausentes;
- não apaga nem esvazia pastas;
- preserva `.env` sem ler ou substituir seu conteúdo;
- preserva prompts personalizados;
- ignora assets oficiais idênticos;
- preserva launcher, prompt ou manual oficial diferente e informa o conflito;
- não toca no conteúdo de entradas, saídas, sessões ou usage.

Sem `-Force`, um conflito permanece intacto. Com `-Force`, somente o launcher,
os quatro prompts oficiais conhecidos e o manual oficial podem ser
substituídos. Outros DOCX permanecem intocados. Compare as versões antes de
usar essa opção. O sync pode ser repetido normalmente ou omitido com
`-SkipSync`.

### 17.2 Git, versões e releases

- `v1.0.0` é o snapshot histórico congelado da primeira release;
- `v1.1.0` adiciona a instalação reproduzível e portátil descrita neste manual;
- `v1.1.1` adiciona sessões interativas sem documentos;
- `V1_SNAPSHOT.md` continua descrevendo especificamente a v1.0.0;
- documentos vivos, como este manual e `PROJECT_STATE.md`, acompanham a versão
  atual;
- tags antigas não devem ser recriadas, movidas ou alteradas.

## 18. Troubleshooting

### 18.1 O launcher não abriu corretamente

Primeiro, leia a mensagem que o launcher mantém visível na janela quando há
erro. Depois:

1. confirme que `C:\IA\api` existe;
2. abra o PowerShell e confirme que o `uv` está disponível:

```powershell
uv --version
```

3. teste a inicialização manualmente:

```powershell
cd C:\IA\api
uv run python application\ia_interativa.py
```

Use a mensagem exibida para investigar a causa. Não reinstale dependências,
apague ambientes ou altere configurações como primeira tentativa.

### 18.2 Atribuí `$env:GEMINI_MODEL`, mas nada apareceu

Isso é normal no PowerShell. Atribuição bem-sucedida não imprime confirmação:

```powershell
$env:GEMINI_MODEL="gemini-3.5-flash"
```

Confira com:

```powershell
$env:GEMINI_MODEL
```

### 18.3 Reiniciei o terminal e a variável sumiu

Variáveis `$env:...` definidas no PowerShell são temporárias daquela sessão.
Para persistência do projeto, registre somente nomes de modelo e credenciais no
`.env` local, nunca na documentação ou no Git.

### 18.4 `No API key was provided`

O provider selecionado não encontrou uma credencial válida. Confirme se o
arquivo é `C:\IA\api\.env`, se a variável correta existe e se a aplicação foi
iniciada pelo projeto. Não cole o valor da chave em logs, issues ou manuais.

### 18.5 O modelo atingiu limite ou quota

A CLI normaliza erros de rate limit/quota e, quando disponível, mostra o tempo
sugerido para nova tentativa. Verifique o painel do provider, aguarde ou troque
de provider/modelo conscientemente. Não presuma que repetir imediatamente ou
forçar fallback structured resolverá o problema.

### 18.6 Warning de permissão em `.pytest_cache`

No Codex ou em outro sandbox pode aparecer aviso de permissão ao acessar
`.pytest_cache`. Verifique o resultado final do pytest: um warning de cache não
é o mesmo que falha de teste. Não altere permissões ou apague arquivos
automaticamente sem confirmar o alvo e a necessidade.

### 18.7 Warning interno do `google-genai`

A suíte conhecida emite um `DeprecationWarning` sobre `_UnionGenericAlias` em
`google.genai.types`. É uma advertência da dependência, não um teste falhando.
Reavalie quando atualizar o SDK; não silencie ou altere código por impulso.

### 18.8 Como saber se o Git está limpo

`git status` deve informar que não há mudanças. `git status --short` sem saída
também significa working tree limpo. Se houver linhas, leia cada status antes
de executar testes, edições ou commits.

### 18.9 Arquivos verdes no VS Code

As cores dependem do tema e da integração Git, mas verde costuma indicar
arquivo novo ou mudança ainda não commitada. A fonte de verdade é:

```powershell
cd C:\IA\api
git status --short
```

Um arquivo untracked aparece com `??`. Não use apenas a cor para decidir se o
repositório está limpo.

### 18.10 Codex aberto em `C:\IA`, Git em `C:\IA\api`

O workspace mais amplo pode estar aberto em `C:\IA`, mas comandos do projeto
devem usar `C:\IA\api` como diretório. Um comando executado no lugar errado
pode não encontrar `.git`, `pyproject.toml`, `.venv` ou os testes.

### 18.11 Mensagem longa ou colada em várias linhas

Não tente improvisar escapes no prompt normal. Digite `multiline` ou `multi`,
cole o texto e finalize com uma linha contendo somente `/fim`.

### 18.12 Segurança de credenciais

Nunca guarde API keys em Markdown, DOCX, scripts de exemplo, commits,
screenshots ou mensagens de suporte. Use placeholders como
`OPENAI_API_KEY=...` e mantenha valores reais somente no ambiente seguro.

Nunca versione nem compartilhe:

- `.env`;
- `Key.txt` ou qualquer arquivo auxiliar de credenciais;
- API keys ou tokens;
- sessões privadas em `<Root>\6_Dados\sessions`;
- arquivos de entrada do usuário;
- outputs que possam conter informação sensível;
- registros de usage quando puderem revelar informação privada.

`.env.example` pode ser compartilhado porque contém somente nomes de variáveis
e placeholders vazios. Cada pessoa deve preencher suas próprias credenciais;
não copie secrets de outra instalação.

### 18.13 O template salvo não existe mais

A aplicação mostra um aviso e continua com Nenhum. A sessão é salva novamente
sem o filename removido. Se o arquivo deveria continuar oficial, confira
`C:\IA\4_Prompts` e as duas linhas de metadata; não selecione outro template
automaticamente para substituir uma intenção diferente.

## 19. Referência rápida

### 19.1 Comandos PowerShell principais

| Objetivo | Comando |
|---|---|
| Clonar instalação padrão | `git clone https://github.com/LeoLimaTHE-dev/ai-engine.git C:\IA\api` |
| Entrar no projeto | `cd C:\IA\api` |
| Preparar workspace | `.\scripts\setup_workspace.ps1` |
| Preparar outra raiz | `.\scripts\setup_workspace.ps1 -Root "D:\IA"` |
| Preparar sem sync | `.\scripts\setup_workspace.ps1 -SkipSync` |
| Sincronizar dependências | `uv sync` |
| Rodar testes offline | `uv run pytest -q` |
| Iniciar a aplicação | `uv run python application\ia_interativa.py` |
| Ver estado Git | `git status` |
| Ver estado compacto | `git status --short` |
| Ver histórico recente | `git log -5 --oneline` |
| Conferir whitespace | `git diff --check` |
| Definir modelo temporário | `$env:GEMINI_MODEL="gemini-3.5-flash"` |
| Consultar modelo temporário | `$env:GEMINI_MODEL` |

### 19.2 Launcher de uso cotidiano

| Arquivo | Localização | Finalidade |
|---|---|---|
| `Iniciar IA.bat` | `C:\IA` | Inicia a aplicação para uso cotidiano. |

### 19.3 Providers e aliases

| Nome principal | Aliases aceitos |
|---|---|
| OpenAI | `openai` |
| Anthropic | `anthropic`, `claude` |
| Gemini | `gemini`, `google` |

Na interface, os nomes exibidos são Gemini, OpenAI e Claude.

### 19.4 Variáveis de ambiente principais

| Variável | Finalidade |
|---|---|
| `OPENAI_API_KEY` | Credencial OpenAI. |
| `ANTHROPIC_API_KEY` | Credencial Anthropic. |
| `GEMINI_API_KEY` | Credencial Gemini. |
| `OPENAI_MODEL` | Modelo OpenAI usado pela operação. |
| `ANTHROPIC_MODEL` | Modelo Anthropic usado pela operação. |
| `GEMINI_MODEL` | Modelo Gemini usado pela operação. |
| `IA_ROOT` | Define a raiz de entrada, saída, prompts, dados e temporários; o launcher gerado já configura essa variável. |
| `AI_PROVIDER_TIMEOUT_SECONDS` | Timeout dos adapters. |
| `AI_PROVIDER_MAX_RETRIES` | Retries do engine onde aplicável. |
| `AI_PROVIDER_RETRY_BASE_DELAY_SECONDS` | Atraso-base do retry. |
| `AI_PROVIDER_RETRY_MAX_DELAY_SECONDS` | Teto do atraso de retry. |

### 19.5 Extensões de entrada

| Categoria | Extensões |
|---|---|
| Texto | `.txt` |
| Markdown | `.md`, `.markdown` |
| Dados tabulares | `.csv`, `.xlsx`, `.xlsm` |
| Documentos | `.docx`, `.pdf` |
| Imagens | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`, `.tiff`, `.tif` |

### 19.6 Formatos de saída

| Formato | Capacidade v1 |
|---|---|
| TXT | Texto UTF-8. |
| MD | Texto Markdown preservado. |
| DOCX | Título opcional + texto. |
| PDF | Título opcional + texto em A4. |
| XLSX | Conteúdo linear ou tabelas estruturadas. |

### 19.7 Comandos da aplicação

| Comando | Efeito |
|---|---|
| `sair` | Salvar e encerrar. |
| `limpar` | Apagar memória da conversa. |
| `uso` | Mostrar uso acumulado. |
| `provider` | Trocar provider. |
| `salvar` | Salvar manualmente. |
| `multiline` / `multi` | Iniciar mensagem multilinha. |
| `/fim` | Encerrar a captura multiline quando estiver sozinho na linha. |

O menu de template existe somente na criação: Enter/`0` significa Nenhum e os
demais itens vêm da metadata dos arquivos oficiais.

### 19.8 Pastas principais

| Local | Conteúdo |
|---|---|
| `C:\IA` | Workspace operacional. |
| `C:\IA\Iniciar IA.bat` | Launcher recomendado para uso cotidiano. |
| `C:\IA\api` | Repositório Git e projeto Python. |
| `C:\IA\2_Entrada` | Arquivos de entrada. |
| `C:\IA\3_Saída` | Arquivos gerados. |
| `C:\IA\4_Prompts` | Templates externos. |
| `C:\IA\6_Dados\sessions` | Sessões JSON. |
| `C:\IA\6_Dados\usage` | Registro CSV de usage. |
| `C:\IA\7_Temporario` | Temporários operacionais. |
| `C:\IA\api\workspace_assets` | Snapshot versionado do launcher e templates; não é operacional. |
| `<Root>\Guia_Ambiente_IA_Multi_Provider_v1.1.1.docx` | Manual humano instalado pelo setup. |

### 19.9 Arquivos e documentos importantes

| Arquivo | Finalidade |
|---|---|
| `C:\IA\Iniciar IA.bat` | Inicia a aplicação sem abrir VS Code ou digitar comandos. |
| `application\ia_interativa.py` | Aplicação interativa oficial. |
| `src\ai_engine\workflow.py` | Workflow livre e estruturado. |
| `src\ai_engine\provider_capabilities.py` | Capability por provider + modelo. |
| `src\ai_engine\structured_schema.py` | Schema canônico. |
| `src\ai_engine\prompts.py` | Carregamento de prompts externos. |
| `README.md` | Visão rápida. |
| `PROJECT_STATE.md` | Estado técnico vivo. |
| `ARCHITECTURE.md` | Arquitetura do pacote. |
| `SYSTEM_ARCHITECTURE.md` | Arquitetura do workspace. |
| `NATIVE_STRUCTURED_OUTPUT_AUDIT.md` | Auditoria e decisões do transporte structured. |
| `HANDOFF_V1.md` | Continuidade para outra IA. |
| `V1_SNAPSHOT.md` | Snapshot histórico da v1. |
| `MANUAL_SOURCE.md` | Fonte viva deste manual humano. |
| `SETUP_WORKSPACE.md` | Procedimento detalhado de instalação e reinstalação. |
| `scripts\setup_workspace.ps1` | Setup idempotente do workspace. |
| `.env.example` | Modelo sem credenciais para criar o `.env` local. |

## 20. Limitações deliberadas da v1

- DOCX e PDF estruturados suportam título e texto, sem tabelas ou imagens
  físicas e sem renderização Markdown avançada.
- Referências de imagens são marcadores para inserção manual.
- Não existe OCR local para PDFs ou imagens.
- A capability native structured usa uma allowlist conservadora de modelos
  comprovados, não descoberta dinâmica completa.
- Não existe fallback automático para legado depois de iniciar uma chamada
  native.
- Todos os providers retornam `str`; não há parsing tipado por SDK/Pydantic.
- `STRUCTURED_OUTPUT_INSTRUCTIONS` permanece também no caminho native.
- Planning acontece antes da escrita, mas não há rollback transacional se um
  exporter falhar depois que outputs anteriores já foram gravados.
- O coletor de pastas não percorre subdiretórios.
- O modo batch é sequencial, não paralelo.
- Sessões persistem contexto textual e caminho de entrada; documentos são
  relidos ao restaurar.
- Templates são escolhidos somente na criação; não há troca durante o chat.
- A CLI não cria, edita ou exclui templates e não possui categorias, favoritos,
  busca ou seleção automática baseada na pergunta.

Essas limitações são escolhas de escopo, não autorização para refatorações
amplas antes de compreender os contratos e testes existentes.

## 21. Continuidade para v2

Para retomar desenvolvimento com outra IA, envie primeiro
`HANDOFF_V1.md`. Ele explica estrutura, comandos, decisões estabilizadas e
procedimento seguro de continuidade.

Depois da tag `v1.0.0`, `V1_SNAPSHOT.md` representa o estado histórico
congelado e não deve ser atualizado para descrever a v2. O
`PROJECT_STATE.md` continua registrando o estado técnico vivo, enquanto este
`MANUAL_SOURCE.md` acompanha a operação humana atual.

Backlog candidato, sem compromisso fechado:

- Rich Documents com seções, paragraphs, tables, images, captions e page
  breaks;
- inserção física de imagens em DOCX/PDF;
- tabelas estruturadas e renderização rica em DOCX/PDF;
- uso de documento existente como modelo visual;
- parsing tipado ou Pydantic somente se o benefício justificar a migração;
- redução das instruções textuais no caminho native;
- rollback transacional de múltiplas escritas;
- capability mais rica por provider e modelo;
- evolução de sessões e contexto;
- batch paralelo e OCR local, após avaliação de custo e risco;
- revisão de scripts legados e futura experiência de launcher.

Ao iniciar a v2:

1. entre em `C:\IA\api` e confirme o Git;
2. rode a suíte offline completa;
3. leia `HANDOFF_V1.md`, `V1_SNAPSHOT.md`, `PROJECT_STATE.md` e o código do
   fluxo afetado;
4. escolha um checkpoint pequeno e compatível;
5. preserve adapters separados quando os SDKs tiverem semânticas diferentes;
6. não execute smoke real nem faça commit sem autorização explícita.
