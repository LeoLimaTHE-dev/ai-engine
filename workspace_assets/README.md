# Assets operacionais versionados

## Finalidade

Esta pasta guarda cópias versionadas dos assets operacionais externos ao
repositório principal. Ela representa os assets da release e permite reconstruir
o workspace futuramente.

Versão operacional, usada no cotidiano:

```text
C:\IA\Iniciar IA.bat
C:\IA\4_Prompts
```

Snapshot versionado e fonte do setup da v1.1.0:

```text
C:\IA\api\workspace_assets
```

## Importante

- O engine não deve usar `workspace_assets\prompts` automaticamente.
- Não altere paths de produção para apontar para esta pasta.
- `workspace_assets` não é a pasta operacional do sistema.
- A cópia existe somente para versionamento e reconstrução.
- `scripts\setup_workspace.ps1` usa estes assets para instalar prompts e o
  manual humano, além de gerar um launcher ajustado à raiz escolhida.
- Antes de uma release, sincronize conscientemente mudanças feitas nos assets
  operacionais com este snapshot.
- Não copie `.env`, `Key.txt`, API keys, sessões, usage, outputs, arquivos de
  entrada, temporários ou `.venv` para esta pasta.

## Restauração conceitual

Em uma reconstrução, prefira executar `scripts\setup_workspace.ps1`. Em termos
conceituais, os arquivos são instalados assim:

```text
workspace_assets\Iniciar IA.bat
-> C:\IA\Iniciar IA.bat

workspace_assets\prompts\*
-> C:\IA\4_Prompts\

workspace_assets\Guia_Ambiente_IA_Multi_Provider_v1.1.0.docx
-> C:\IA\Guia_Ambiente_IA_Multi_Provider_v1.1.0.docx
```

O launcher versionado contém placeholders e não deve ser usado diretamente. O
setup materializa esses placeholders sem mudar os paths usados pelo engine. O
manual usa a mesma política segura: conteúdo diferente é preservado sem
`-Force`, e outros DOCX nunca são removidos.
