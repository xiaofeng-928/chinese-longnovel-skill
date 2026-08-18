[CmdletBinding()]
param(
    [ValidateSet("codex", "claude", "both")]
    [string]$Platform = "both",
    [string]$Repository = "https://github.com/xiaofeng-928/chinese-longnovel-skill.git",
    [string]$Ref = "master",
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }),
    [string]$ClaudeHome = $(if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME ".claude" })
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required. Install Git, then run this command again."
}

function Install-MyNovel {
    param(
        [Parameter(Mandatory)]
        [string]$AgentName,
        [Parameter(Mandatory)]
        [string]$AgentHome
    )

    $skillsDir = Join-Path $AgentHome "skills"
    $target = Join-Path $skillsDir "my-novel"
    New-Item -ItemType Directory -Force -Path $skillsDir | Out-Null

    if (Test-Path -LiteralPath $target) {
        if (-not (Test-Path -LiteralPath (Join-Path $target ".git"))) {
            throw "Target already exists and is not a Git checkout: $target"
        }

        Write-Host "Updating MyNovel for $AgentName at $target"
        & git -C $target fetch --depth 1 origin $Ref
        if ($LASTEXITCODE -ne 0) { throw "Git fetch failed for $AgentName." }
        & git -C $target merge --ff-only FETCH_HEAD
        if ($LASTEXITCODE -ne 0) { throw "The existing checkout cannot be fast-forwarded: $target" }
    }
    else {
        Write-Host "Installing MyNovel for $AgentName at $target"
        & git clone --depth 1 --branch $Ref $Repository $target
        if ($LASTEXITCODE -ne 0) { throw "Git clone failed for $AgentName." }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $target "SKILL.md"))) {
        throw "Installation is incomplete: SKILL.md was not found at $target"
    }

    Write-Host "Installed: $target"
}

if ($Platform -in @("codex", "both")) {
    Install-MyNovel -AgentName "Codex" -AgentHome $CodexHome
}

if ($Platform -in @("claude", "both")) {
    Install-MyNovel -AgentName "Claude Code" -AgentHome $ClaudeHome
}

Write-Host "Restart the selected agent so it can discover the skill."
