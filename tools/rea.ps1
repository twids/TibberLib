param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ReaArguments
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$nodePath = Join-Path $projectRoot 'work/tools/node_modules/node/bin/node.exe'
$reaPath = Join-Path $projectRoot 'work/tools/node_modules/rea-agents/scripts/rea.mjs'
$jdkPath = 'C:/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot'
if (-not (Test-Path $nodePath) -or -not (Test-Path $reaPath)) {
    throw 'Install local Node 24 and REA into work/tools first.'
}
$env:JAVA_HOME = $jdkPath
$env:REA_JADX_MCP_JAR = Join-Path $projectRoot 'work/jadx-headless-mcp.jar'
& $nodePath $reaPath @ReaArguments
exit $LASTEXITCODE
