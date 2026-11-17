<#
.SYNOPSIS
    Faz 5 Bolum 6.1: Backgammon yonetilen derlemelerini ve ONNX Runtime native
    eklentisini Unity projesine kopyalar.

.DESCRIPTION
    Betik **idempotent**tir: kaynak dosya hedeftekinden yeni degilse kopyalamaz.
    Kopyalama **elle** yapilmaz; tek dogru yol budur.

    Kopyalananlar:
        Backgammon.Core.dll          -> Assets/Plugins/Managed/
        Backgammon.Inference.dll     -> Assets/Plugins/Managed/
        Backgammon.UI.dll            -> Assets/Plugins/Managed/
        Microsoft.ML.OnnxRuntime.dll -> Assets/Plugins/Managed/
        onnxruntime.dll              -> Assets/Plugins/x86_64/
        onnxruntime_providers_shared.dll -> Assets/Plugins/x86_64/

    Ayrica model ve bearoff veritabani StreamingAssets'e kopyalanir:
        ml/runs/stage_d/onnx/model_v5.onnx -> Assets/StreamingAssets/models/model.onnx
        ml/artifacts/bearoff1_v1.bin       -> Assets/StreamingAssets/bearoff/bearoff1_v1.bin

.PARAMETER UnityProject
    Unity projesinin koku. Varsayilan: F:\Projects\Unity\Tavla3D

.PARAMETER Configuration
    Derleme yapilandirmasi. Varsayilan: Release

.PARAMETER SkipBuild
    Verilirse dotnet build calistirilmaz; yalnizca var olan ciktilar kopyalanir.

.PARAMETER OnnxRuntimeVersion
    Microsoft.ML.OnnxRuntime paket surumu. Varsayilan: 1.23.2
    (Backgammon.Inference.csproj ile **ayni** olmalidir.)

.EXAMPLE
    pwsh -File tools/sync-unity-plugins.ps1
#>
[CmdletBinding()]
param(
    [string] $UnityProject = "F:\Projects\Unity\Tavla3D",
    [string] $Configuration = "Release",
    [switch] $SkipBuild,
    [string] $OnnxRuntimeVersion = "1.23.2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = Split-Path -Parent $PSScriptRoot
Write-Host "depo kokü      : $repo"
Write-Host "unity projesi  : $UnityProject"

if (-not (Test-Path (Join-Path $UnityProject "ProjectSettings\ProjectVersion.txt"))) {
    throw "Unity projesi bulunamadi: $UnityProject"
}

if (-not $SkipBuild) {
    Write-Host "`n[1/3] dotnet build ($Configuration) ..."
    & dotnet build (Join-Path $repo "TavlaAI_Project.slnx") -c $Configuration --nologo -v q
    if ($LASTEXITCODE -ne 0) { throw "dotnet build basarisiz (exit $LASTEXITCODE)" }
}
else {
    Write-Host "`n[1/3] dotnet build atlandi (-SkipBuild)"
}

$managedDir = Join-Path $UnityProject "Assets\Plugins\Managed"
$nativeDir = Join-Path $UnityProject "Assets\Plugins\x86_64"
$modelsDir = Join-Path $UnityProject "Assets\StreamingAssets\models"
$bearoffDir = Join-Path $UnityProject "Assets\StreamingAssets\bearoff"
foreach ($d in @($managedDir, $nativeDir, $modelsDir, $bearoffDir)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

$nuget = if ($env:NUGET_PACKAGES) { $env:NUGET_PACKAGES } else { Join-Path $env:USERPROFILE ".nuget\packages" }

$plan = @(
    @{ Src = Join-Path $repo "Backgammon.Core\bin\$Configuration\netstandard2.1\Backgammon.Core.dll"; Dst = Join-Path $managedDir "Backgammon.Core.dll" }
    @{ Src = Join-Path $repo "Backgammon.Inference\bin\$Configuration\netstandard2.1\Backgammon.Inference.dll"; Dst = Join-Path $managedDir "Backgammon.Inference.dll" }
    @{ Src = Join-Path $repo "Backgammon.UI\bin\$Configuration\netstandard2.1\Backgammon.UI.dll"; Dst = Join-Path $managedDir "Backgammon.UI.dll" }
    @{ Src = Join-Path $nuget "microsoft.ml.onnxruntime.managed\$OnnxRuntimeVersion\lib\netstandard2.0\Microsoft.ML.OnnxRuntime.dll"; Dst = Join-Path $managedDir "Microsoft.ML.OnnxRuntime.dll" }
    @{ Src = Join-Path $nuget "microsoft.ml.onnxruntime\$OnnxRuntimeVersion\runtimes\win-x64\native\onnxruntime.dll"; Dst = Join-Path $nativeDir "onnxruntime.dll" }
    @{ Src = Join-Path $nuget "microsoft.ml.onnxruntime\$OnnxRuntimeVersion\runtimes\win-x64\native\onnxruntime_providers_shared.dll"; Dst = Join-Path $nativeDir "onnxruntime_providers_shared.dll" }
    @{ Src = Join-Path $repo "ml\runs\stage_d\onnx\model_v5.onnx"; Dst = Join-Path $modelsDir "model.onnx" }
    @{ Src = Join-Path $repo "ml\artifacts\bearoff1_v1.bin"; Dst = Join-Path $bearoffDir "bearoff1_v1.bin" }
)

Write-Host "`n[2/3] kopyalama ..."
$copied = 0
$skipped = 0
foreach ($item in $plan) {
    if (-not (Test-Path $item.Src)) {
        throw "kaynak yok: $($item.Src)"
    }

    $needsCopy = $true
    if (Test-Path $item.Dst) {
        $srcTime = (Get-Item $item.Src).LastWriteTimeUtc
        $dstTime = (Get-Item $item.Dst).LastWriteTimeUtc
        $srcLen = (Get-Item $item.Src).Length
        $dstLen = (Get-Item $item.Dst).Length
        if ($srcTime -le $dstTime -and $srcLen -eq $dstLen) { $needsCopy = $false }
    }

    if ($needsCopy) {
        Copy-Item -LiteralPath $item.Src -Destination $item.Dst -Force
        Write-Host ("  kopyalandi : {0}" -f (Split-Path -Leaf $item.Dst))
        $copied++
    }
    else {
        Write-Host ("  guncel     : {0}" -f (Split-Path -Leaf $item.Dst))
        $skipped++
    }
}

Write-Host "`n[3/3] ozet"
Write-Host "  kopyalanan : $copied"
Write-Host "  guncel     : $skipped"
Write-Host "  toplam     : $($plan.Count)"

# Surum kontrolu: ORT native ile yonetilen ayni surum mu?
$nativeVersion = (Get-Item (Join-Path $nativeDir "onnxruntime.dll")).VersionInfo.FileVersion
Write-Host "  onnxruntime.dll surumu : $nativeVersion (beklenen $OnnxRuntimeVersion)"
