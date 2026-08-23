# Preparação reproduzível do workspace

Este guia prepara o workspace operacional do `ai-engine` a partir de um clone
do repositório. O contrato da v1.1.0 é:

```text
<Root>\api
```

O setup não move nem duplica o repositório. Esse fluxo foi introduzido na
v1.1.0 e permanece inalterado na v1.1.1, que acrescenta sessões interativas sem
documentos à aplicação.

## Pré-requisitos

- Windows com PowerShell;
- Git para obter o repositório;
- `uv` disponível no `PATH`;
- acesso à rede durante `uv sync`, salvo uso de `-SkipSync`.

O projeto declara Python 3.14 ou mais recente. O `uv` pode localizar ou
provisionar a versão adequada; não é necessário ativar `.venv` manualmente.

## Clone recomendado

Escolha a raiz e clone diretamente para a subpasta `api`:

```powershell
git clone <URL_DO_REPOSITORIO> C:\IA\api
cd C:\IA\api
```

Para outra raiz:

```powershell
git clone <URL_DO_REPOSITORIO> D:\IA\api
cd D:\IA\api
```

## Executar o setup

Quando o repositório já está em `<Root>\api`, a raiz é inferida:

```powershell
.\scripts\setup_workspace.ps1
```

Também é possível declarar a raiz explicitamente:

```powershell
.\scripts\setup_workspace.ps1 -Root "D:\IA"
```

O caminho informado precisa corresponder ao pai real do repositório. O setup
falha com uma mensagem clara se o clone não estiver em `<Root>\api`.

Por padrão, o setup verifica `uv` e executa `uv sync`. Essa operação pode usar
rede e baixar Python ou dependências. Para preparar apenas diretórios e assets:

```powershell
.\scripts\setup_workspace.ps1 -SkipSync
```

## O que é criado

- diretórios de entrada, saída, prompts, sessões, usage e temporários;
- diretórios organizacionais `1_Projetos` e `5_Modelos`;
- os quatro prompts oficiais, a partir de `workspace_assets\prompts`;
- `<Root>\Guia_Ambiente_IA_Multi_Provider_v1.1.1.docx`, a partir do manual
  humano versionado em `workspace_assets`;
- `<Root>\Iniciar IA.bat`, com `IA_ROOT` e repo ajustados à instalação;
- `.env`, copiado de `.env.example`, somente quando ainda não existe.

Depois do setup, preencha manualmente no `.env` apenas as credenciais dos
providers que pretende usar. Nunca copie secrets de outra pessoa e não coloque
keys em documentação, launcher ou Git.

## Conflitos e `-Force`

O setup preserva launcher, prompts e manual oficial quando o conteúdo é
diferente. Para substituir conscientemente somente os quatro prompts oficiais,
o launcher e o manual humano oficial:

```powershell
.\scripts\setup_workspace.ps1 -Force
```

`-Force` nunca substitui `.env`, não remove prompts personalizados ou outros
DOCX e não toca em entradas, saídas, sessões ou usage. Ao atualizar da v1.1.0
para a v1.1.1, o manual antigo pode permanecer ao lado do novo; o setup não o
remove automaticamente.

## Idempotência

O setup pode ser executado novamente com segurança. Ele cria somente o que
falta, ignora conteúdo idêntico e preserva conflitos sem `-Force`. Diretórios
existentes nunca são apagados ou esvaziados. `uv sync` pode ser repetido; use
`-SkipSync` quando não quiser executá-lo.

## Uso após a instalação

Preencha o `.env` e dê dois cliques em:

```text
<Root>\Iniciar IA.bat
```

O launcher define `IA_ROOT`, entra no repositório e inicia a aplicação com
`uv`. Ele não sincroniza dependências, não roda testes e não altera Git.
O manual humano instalado fica em
`<Root>\Guia_Ambiente_IA_Multi_Provider_v1.1.1.docx`.

## Troubleshooting

- `uv não foi encontrado`: instale o `uv`, abra um novo PowerShell e confirme
  com `uv --version`.
- `Estrutura incompatível`: confirme que o repositório está diretamente em
  `<Root>\api`; o setup não o moverá.
- Conflito de asset: preserve o arquivo, compare as versões e use `-Force`
  somente se quiser restaurar o asset oficial.
- Falha no `uv sync`: verifique rede, proxy e a mensagem do próprio `uv`; os
  dados existentes no workspace permanecem preservados.
- `.env` já existe: o setup não lê nem substitui esse arquivo.

O setup não chama providers e não valida API keys.
