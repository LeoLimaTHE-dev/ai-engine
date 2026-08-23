[CmdletBinding()]
param(
    [Parameter()]
    [string]$Root,

    [Parameter()]
    [switch]$SkipSync,

    [Parameter()]
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Write-SetupMessage {
    param(
        [Parameter(Mandatory = $true)][string]$Kind,
        [Parameter(Mandatory = $true)][string]$Message
    )

    Write-Host "[$Kind] $Message"
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (Test-Path -LiteralPath $Path -PathType Container) {
        Write-SetupMessage "OK" "Diretorio ja existe: $Path"
        return
    }

    if (Test-Path -LiteralPath $Path) {
        throw "[ERRO] O caminho existe, mas nao e um diretorio: $Path"
    }

    New-Item -ItemType Directory -Path $Path | Out-Null
    Write-SetupMessage "CRIADO" $Path
}

function Install-FileSafely {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Destination)) {
        Copy-Item -LiteralPath $Source -Destination $Destination
        Write-SetupMessage "COPIADO" "$Label -> $Destination"
        return
    }

    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    $destinationHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash

    if ($sourceHash -eq $destinationHash) {
        Write-SetupMessage "IGNORADO" "Conteudo identico: $Destination"
        return
    }

    if ($Force) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        Write-SetupMessage "COPIADO" "$Label substituido com -Force: $Destination"
        return
    }

    Write-SetupMessage "CONFLITO" "Arquivo existente diferente foi preservado: $Destination"
}

function Install-GeneratedTextFileSafely {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedContent,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (Test-Path -LiteralPath $Destination) {
        $currentContent = [System.IO.File]::ReadAllText($Destination)

        if ($currentContent -eq $ExpectedContent) {
            Write-SetupMessage "IGNORADO" "Conteudo identico: $Destination"
            return
        }

        if (-not $Force) {
            Write-SetupMessage "CONFLITO" "Arquivo existente diferente foi preservado: $Destination"
            return
        }
    }

    [System.IO.File]::WriteAllText(
        $Destination,
        $ExpectedContent,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-SetupMessage "CRIADO" "$Label -> $Destination"
}

try {
    $repoDirectory = Get-NormalizedPath (
        Join-Path $PSScriptRoot ".."
    )

    if ((Split-Path -Leaf $repoDirectory) -ine "api") {
        throw "[ERRO] O repositorio deve estar diretamente em <Root>\api. Encontrado: $repoDirectory"
    }

    if ([string]::IsNullOrWhiteSpace($Root)) {
        $workspaceRoot = Get-NormalizedPath (Split-Path -Parent $repoDirectory)
    }
    else {
        if (-not [System.IO.Path]::IsPathRooted($Root)) {
            throw "[ERRO] -Root deve ser um caminho absoluto."
        }

        $workspaceRoot = Get-NormalizedPath $Root
    }

    $expectedRepoDirectory = Get-NormalizedPath (
        Join-Path $workspaceRoot "api"
    )

    if ($repoDirectory -ine $expectedRepoDirectory) {
        throw (
            "[ERRO] Estrutura incompativel. Este setup exige o repositorio em " +
            "<Root>\api.`nRepositorio: $repoDirectory`nEsperado: $expectedRepoDirectory`n" +
            "O setup nao move nem copia o repositorio."
        )
    }

    Write-SetupMessage "OK" "Repositorio: $repoDirectory"
    Write-SetupMessage "OK" "IA_ROOT: $workspaceRoot"

    $directories = @(
        "1_Projetos",
        "2_Entrada",
        "2_Entrada\batch_teste",
        "3_Saída",
        "4_Prompts",
        "5_Modelos",
        "6_Dados",
        "6_Dados\sessions",
        "6_Dados\usage",
        "7_Temporario"
    )

    foreach ($relativeDirectory in $directories) {
        Ensure-Directory (Join-Path $workspaceRoot $relativeDirectory)
    }

    $promptSourceDirectory = Join-Path $repoDirectory "workspace_assets\prompts"
    $promptDestinationDirectory = Join-Path $workspaceRoot "4_Prompts"
    $officialPrompts = @(
        "resumir.md",
        "analisar_documentos.md",
        "comparar_arquivos.md",
        "relatorio_multimodal_com_imagens.md"
    )

    foreach ($promptName in $officialPrompts) {
        $source = Join-Path $promptSourceDirectory $promptName
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "[ERRO] Asset oficial ausente: $source"
        }

        Install-FileSafely `
            -Source $source `
            -Destination (Join-Path $promptDestinationDirectory $promptName) `
            -Label "Prompt oficial"
    }

    $manualName = "Guia_Ambiente_IA_Multi_Provider_v1.1.0.docx"
    $manualSource = Join-Path $repoDirectory "workspace_assets\$manualName"
    if (-not (Test-Path -LiteralPath $manualSource -PathType Leaf)) {
        throw "[ERRO] Manual oficial ausente: $manualSource"
    }

    Install-FileSafely `
        -Source $manualSource `
        -Destination (Join-Path $workspaceRoot $manualName) `
        -Label "Manual humano oficial"

    $launcherTemplatePath = Join-Path $repoDirectory "workspace_assets\Iniciar IA.bat"
    if (-not (Test-Path -LiteralPath $launcherTemplatePath -PathType Leaf)) {
        throw "[ERRO] Template do launcher ausente: $launcherTemplatePath"
    }

    $launcherContent = [System.IO.File]::ReadAllText($launcherTemplatePath)
    if (
        -not $launcherContent.Contains("__IA_ROOT__") -or
        -not $launcherContent.Contains("__REPO_DIR__")
    ) {
        throw "[ERRO] O launcher versionado nao contem os placeholders esperados."
    }

    $launcherContent = $launcherContent.Replace("__IA_ROOT__", $workspaceRoot)
    $launcherContent = $launcherContent.Replace("__REPO_DIR__", $repoDirectory)
    Install-GeneratedTextFileSafely `
        -ExpectedContent $launcherContent `
        -Destination (Join-Path $workspaceRoot "Iniciar IA.bat") `
        -Label "Launcher operacional"

    $environmentExample = Join-Path $repoDirectory ".env.example"
    $environmentFile = Join-Path $repoDirectory ".env"

    if (-not (Test-Path -LiteralPath $environmentExample -PathType Leaf)) {
        throw "[ERRO] Arquivo .env.example ausente: $environmentExample"
    }

    if (Test-Path -LiteralPath $environmentFile) {
        Write-SetupMessage "IGNORADO" ".env existente foi preservado sem leitura."
    }
    else {
        Copy-Item -LiteralPath $environmentExample -Destination $environmentFile
        Write-SetupMessage "CRIADO" ".env criado a partir de .env.example."
    }

    Write-SetupMessage "AVISO" "Preencha manualmente as credenciais no .env. O setup nao valida nem exibe chaves."

    if ($SkipSync) {
        Write-SetupMessage "IGNORADO" "uv sync desabilitado por -SkipSync."
    }
    else {
        if ($null -eq (Get-Command "uv" -ErrorAction SilentlyContinue)) {
            throw "[ERRO] uv nao foi encontrado. Instale o uv e execute o setup novamente."
        }

        Write-SetupMessage "AVISO" "uv sync pode usar rede e baixar Python/dependencias."
        Push-Location $repoDirectory
        try {
            & uv sync
            if ($LASTEXITCODE -ne 0) {
                throw "[ERRO] uv sync terminou com codigo $LASTEXITCODE."
            }
        }
        finally {
            Pop-Location
        }
        Write-SetupMessage "OK" "uv sync concluido."
    }

    Write-Host ""
    Write-SetupMessage "OK" "Workspace preparado com sucesso."
    Write-Host "Launcher: $(Join-Path $workspaceRoot 'Iniciar IA.bat')"
    Write-Host "Entrada: $(Join-Path $workspaceRoot '2_Entrada')"
    Write-Host "Saida: $(Join-Path $workspaceRoot '3_Saída')"
    Write-Host "Prompts: $(Join-Path $workspaceRoot '4_Prompts')"
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
